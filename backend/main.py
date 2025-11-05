from fastapi import FastAPI, File, UploadFile, Form
import os
import shutil
from tortoise.contrib.fastapi import register_tortoise
from fastapi import HTTPException
from backend.models import User
from tortoise.transactions import in_transaction
from backend.deepface_utils import reconhecer_usuario
from backend.models import Log

app = FastAPI()
UPLOAD_FOLDER = 'backend/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "API de reconhecimento facial ativa com sucesso!"}


# Este endpoint já insere no banco e retorna o usuário criado.
@app.post("/usuario")
async def criar_usuario(
    nome: str = Form(...), 
    nivel_seguranca: int = Form(...), 
    division: str = Form(...), 
    file: UploadFile = File(...)
    ):

    # Verifica se o nível está correto
    if nivel_seguranca not in [1, 2, 3]:
        return {"erro": "O nível de segurança deve ser 1, 2 ou 3."}

    file_ext = os.path.splitext(file.filename)[1]
    file_dest = os.path.join(UPLOAD_FOLDER, f"{nome}_{nivel_seguranca}{file_ext}")
    with open(file_dest, "wb") as dest:
        dest.write(await file.read())
        

    async with in_transaction():
        user = await User.create(
            nome=nome,
            nivel_seguranca=nivel_seguranca,
            division=division,
            image_path=file_dest
        )
        return {"id": user.id, 
                "nome": user.nome, 
                "nivel_seguranca": user.nivel_seguranca,
                "division": user.division,
                "image_path": user.image_path,
                }
    

# Isso retorna todos os usuários cadastrados, ajudando a validar facilmente o banco e a visualização dos dados pela API.
@app.get("/usuarios")
async def listar_usuarios():
    usuarios = await User.all().values(
        "id", 
        "nome", 
        "nivel_seguranca", 
        "division", 
        "image_path")
    return usuarios

# Endpoint de autenticação facial
@app.post("/autenticar")
async def autenticar(file: UploadFile = File(...)):
    UPLOAD_TEMP = "backend/uploads/temp"
    os.makedirs(UPLOAD_TEMP, exist_ok=True)
    temp_path = os.path.join(UPLOAD_TEMP, file.filename)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Carregar todos os usuários e paths das imagens
    usuarios = await User.all().values("id", "nome", "nivel_seguranca", "image_path")
    paths = [u["image_path"] for u in usuarios if u["image_path"]]
    result = reconhecer_usuario(temp_path, paths)
    os.remove(temp_path)

    # Identificar usuário pelo caminho da imagem
    usuario = next((u for u in usuarios if u["image_path"] == result["db_img"]), None)
    
    # Log da tentativa
    await Log.create(
        nome=usuario["nome"] if usuario else None,
        nivel_seguranca=usuario["nivel_seguranca"] if usuario else None,
        acesso=bool(result and usuario),
        msg=("Acesso permitido" if result and usuario else "Usuário não reconhecido ou acesso negado")
    )

    if not result:
        return {"acesso": False, "msg": "Usuário não reconhecido!"}
    if usuario:
        return {
            "acesso": True,
            "nome": usuario["nome"],
            "nivel_seguranca": usuario["nivel_seguranca"],
            "distance": result["distance"]
        }
    else:
        return {
            "acesso": False, 
            "msg": "Usuário não encontrado no banco!"
        }

# Para limpar todos os usuários (útil para testes)
@app.delete("/usuarios/apagar_todos")
async def apagar_todos():
    await User.all().delete()
    return {"resultado": "Todos os usuários removidos."}

# Listar logs de acesso (Para que eu tenha controle das tentativas de acesso)
@app.get("/logs")
async def listar_logs():
    return await Log.all().order_by("-timestamp").values()


# Configuração do Tortoise ORM
register_tortoise(
    app,
    db_url="sqlite://backend/db.sqlite3",
    modules={"models": ["backend.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)
