# -*- coding: utf-8 -*-
from uuid import uuid4
from typing import List, Optional
from os import getenv
from typing_extensions import Annotated

from fastapi import Depends, FastAPI
from starlette.responses import RedirectResponse
from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend
from .model import Note, CreateNoteRequest

from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME

resource = Resource(attributes={
    SERVICE_NAME: "notes-api"
})
trace.set_tracer_provider(TracerProvider(resource=resource))
big_pipe_tracer = trace.get_tracer(__name__)
cloud_trace_span_exporter = CloudTraceSpanExporter()
span_processor = BatchSpanProcessor(cloud_trace_span_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)


app = FastAPI()

my_backend: Optional[Backend] = None


def get_backend() -> Backend:
    global my_backend  # pylint: disable=global-statement
    if my_backend is None:
        backend_type = getenv('BACKEND', 'memory')
        print(backend_type)
        if backend_type == 'redis':
            my_backend = RedisBackend()
        elif backend_type == 'gcs':
            my_backend = GCSBackend()
        else:
            my_backend = MemoryBackend()
    return my_backend


@app.get('/')
def redirect_to_notes() -> None:
    with big_pipe_tracer.start_as_current_span('redirect_to_notes') as span:
        return RedirectResponse(url='/notes')


@app.get('/notes')
def get_notes(backend: Annotated[Backend, Depends(get_backend)]) -> List[Note]:
    with big_pipe_tracer.start_as_current_span('get_notes') as span:
        keys = backend.keys()
        Notes = []
        for key in keys:
            Notes.append(backend.get(key))
        return Notes


@app.get('/notes/{note_id}')
def get_note(note_id: str,
             backend: Annotated[Backend, Depends(get_backend)]) -> Note:
    with big_pipe_tracer.start_as_current_span('get_note') as span:
        return backend.get(note_id)


@app.put('/notes/{note_id}')
def update_note(note_id: str,
                request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> None:
    with big_pipe_tracer.start_as_current_span('update_note') as span:
        backend.set(note_id, request)


@app.post('/notes')
def create_note(request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> str:
    with big_pipe_tracer.start_as_current_span('create_note') as span:
        note_id = str(uuid4())
        backend.set(note_id, request)
        span.set_attribute('note_id', note_id)
        span.set_attribute('request', request.title)
        return note_id


FastAPIInstrumentor.instrument_app(app)