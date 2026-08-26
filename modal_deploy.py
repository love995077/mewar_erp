import modal

# 1. Modal App ka naam define karna
app = modal.App("mewar-erp-backend")

history_store = modal.Dict.from_name("mewar-chat-history", create_if_missing=True)

# 2. Cloud environment taiyar karna (Libraries install karna)
image = (
    modal.Image.debian_slim(python_version="3.11") # <--- Python version set kar di
    .pip_install(
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pymysql",
        "cryptography",
        "python-dotenv",
        "rapidfuzz",
        "openai",
        "pydantic",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "python-multipart",
        "streamlit",
        "fastembed==0.3.1",
        "faiss-cpu",
        "numpy",
        "APScheduler==3.10.1",
        "requests>=2.31"
    )
    .add_local_python_source("app")
)

# 3. FastAPI ko Modal ke saath jodna
@app.function(image=image,secrets=[modal.Secret.from_name("mewar-erp-backend")],min_containers=1)
@modal.asgi_app()
def serve():
    from app.main import app as fastapi_app
    return fastapi_app