from __future__ import annotations

from io import BytesIO

from openai import OpenAI


client = OpenAI()


def create_user_vector_store(file_bytes: bytes, filename: str) -> str:
    uploaded_file = client.files.create(
        file=(filename, BytesIO(file_bytes)),
        purpose="assistants",
    )

    vector_store = client.vector_stores.create(
        name="user-uploaded-document"
    )

    client.vector_stores.files.create(
        vector_store_id=vector_store.id,
        file_id=uploaded_file.id,
    )

    return vector_store.id
