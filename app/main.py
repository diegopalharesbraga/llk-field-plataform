import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


APP_NAME = "LLK Field Platform"
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

ws_connections: list[WebSocket] = []


class AssetUpdate(BaseModel):
    situacao_campo: Optional[str] = None
    data_proxima_revisao: Optional[str] = None
    responsavel_manutencao: Optional[str] = None
    observacao: Optional[str] = None


class EventCreate(BaseModel):
    tipo_evento: str
    descricao: str
    responsavel: Optional[str] = None


def hoje():
    return date.today()


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calcular_status_revisao(data_revisao: Optional[str]):
    if not data_revisao:
        return 99999, "Sem data"

    alvo = date.fromisoformat(data_revisao)
    dias = (alvo - hoje()).days

    if dias < 0:
        return dias, "Vencida"

    if dias <= 30:
        return dias, "Proxima"

    return dias, "Em dia"


async def broadcast(event: str, payload: dict | None = None):
    mensagem = {
        "event": event,
        "payload": payload or {},
        "time": agora(),
    }

    conexoes_mortas = []

    for ws in ws_connections:
        try:
            await ws.send_json(mensagem)
        except Exception:
            conexoes_mortas.append(ws)

    for ws in conexoes_mortas:
        if ws in ws_connections:
            ws_connections.remove(ws)


PRODUTOS = [
    "RADEC LLK-100",
    "RADEC LLK-300",
    "RADEC Guard Pro",
    "Sensor de Rasgo RS-20",
    "Painel de Monitoramento PM-900",
]

COMERCIAIS = [
    "Mariana Costa",
    "Bruno Lima",
    "Ana Paula",
    "Rafael Mendes",
    "Diego Torres",
]

ENGENHEIROS = [
    "Eng. Lucas",
    "Eng. Sofia",
    "Eng. Mateus",
    "Eng. Helena",
]

ETAPAS_ABERTAS = [
    "Lead qualificado",
    "Diagnostico tecnico",
    "Proposta enviada",
    "Negociacao",
    "Follow-up atrasado",
]

CLIENTES_VENDIDOS = [
    ("Alfa Mineracao", "Carlos Henrique", "(31) 99910-2200", "Av. Amazonas, 1200", "Belo Horizonte", "MG", -19.9167, -43.9345),
    ("Beta Siderurgia", "Fernanda Duarte", "(11) 98822-4433", "Rua Funchal, 320", "Sao Paulo", "SP", -23.5505, -46.6333),
    ("Gama Energia", "Rodrigo Alves", "(21) 97740-8811", "Av. Rio Branco, 45", "Rio de Janeiro", "RJ", -22.9068, -43.1729),
    ("Delta Agritech", "Joao Meireles", "(62) 99660-2100", "Av. T-9, 880", "Goiania", "GO", -16.6869, -49.2648),
    ("Epsilon Alimentos", "Renata Lopes", "(41) 98800-1199", "Rua XV de Novembro, 450", "Curitiba", "PR", -25.4284, -49.2733),
    ("Zeta Celulose", "Patricia Nunes", "(71) 98850-3300", "Av. Tancredo Neves, 120", "Salvador", "BA", -12.9777, -38.5016),
    ("Sigma Logistica", "Marcelo Vieira", "(51) 97788-4411", "Av. Borges de Medeiros, 880", "Porto Alegre", "RS", -30.0346, -51.2177),
    ("Omega Quimica", "Luciana Ferraz", "(81) 99920-2221", "Av. Boa Viagem, 1000", "Recife", "PE", -8.0476, -34.8770),
    ("Mineracao Serra Azul", "Andre Sales", "(31) 98450-1001", "Rodovia MG-050, km 60", "Itauna", "MG", -20.0753, -44.5764),
    ("Vale Norte Operacoes", "Beatriz Paiva", "(94) 98120-4000", "Estrada Industrial, 450", "Parauapebas", "PA", -6.0675, -49.9023),
    ("Carajas Processos", "Rafael Porto", "(94) 99211-5511", "Av. Liberdade, 240", "Maraba", "PA", -5.3686, -49.1178),
    ("Nordeste Cimentos", "Camila Rocha", "(85) 98888-7711", "BR-116, km 18", "Fortaleza", "CE", -3.7319, -38.5267),
    ("SulMetal Componentes", "Eduardo Ramos", "(47) 99930-9090", "Rua Industrial, 700", "Joinville", "SC", -26.3044, -48.8487),
    ("Pantanal Fertilizantes", "Helena Martins", "(67) 99610-3030", "Av. Afonso Pena, 900", "Campo Grande", "MS", -20.4697, -54.6201),
    ("Bahia Minerios", "Nicolas Freitas", "(77) 98844-2210", "Av. Minas Gerais, 150", "Caetite", "BA", -14.0696, -42.4755),
    ("Amazonas Graos", "Paula Menezes", "(92) 99444-1212", "Av. Djalma Batista, 500", "Manaus", "AM", -3.1190, -60.0217),
    ("Centro-Oeste Bioenergia", "Gustavo Nery", "(65) 99990-7000", "Av. CPA, 780", "Cuiaba", "MT", -15.6014, -56.0979),
    ("Espirito Santo Portos", "Larissa Fontes", "(27) 98870-3020", "Av. Jeronimo Monteiro, 330", "Vitoria", "ES", -20.3155, -40.3128),
    ("Parana Papel e Celulose", "Thiago Moura", "(42) 99111-8888", "Rua das Araucarias, 55", "Ponta Grossa", "PR", -25.0994, -50.1583),
    ("Maranhao Graneis", "Isabela Prado", "(98) 98222-3030", "Av. dos Holandeses, 880", "Sao Luis", "MA", -2.5307, -44.3068),
]

NEGOCIOS_ABERTOS = [
    ("Prospecto Atlantico Cargas", "Marcio Neves", "(27) 99000-1000", "Porto de Tubarao", "Vitoria", "ES", -20.2900, -40.2500),
    ("Prospecto Cerrado Mining", "Aline Ribeiro", "(62) 99111-9000", "Distrito Industrial", "Anapolis", "GO", -16.3285, -48.9534),
    ("Prospecto Litoral Granitos", "Vitor Campos", "(73) 99222-1010", "Rodovia BA-001", "Ilheus", "BA", -14.7935, -39.0464),
    ("Prospecto Norte Fertilizantes", "Monica Reis", "(91) 99333-2020", "Av. Augusto Montenegro", "Belem", "PA", -1.4558, -48.4902),
    ("Prospecto Rio Aco", "Felipe Andrade", "(24) 99444-3030", "Distrito Metalurgico", "Volta Redonda", "RJ", -22.5231, -44.1040),
    ("Prospecto Sul Graos", "Livia Torres", "(54) 99555-4040", "BR-285, km 120", "Passo Fundo", "RS", -28.2636, -52.4091),
    ("Prospecto Nordeste Portos", "Henrique Maia", "(84) 99666-5050", "Av. Portuaria, 100", "Natal", "RN", -5.7793, -35.2009),
    ("Prospecto Triangulo Bio", "Bianca Melo", "(34) 99777-6060", "Distrito Industrial", "Uberlandia", "MG", -18.9146, -48.2754),
]

POINTS = []
EVENTS = []
def valor_venda(index):
    return 38000 + index * 9300


def proximo_evento_id():
    return len(EVENTS) + 1


def registrar_evento(asset_id, open_deal_id, tipo_evento, descricao, responsavel, origem):
    EVENTS.append(
        {
            "id": proximo_evento_id(),
            "asset_id": asset_id,
            "deal_id": open_deal_id,
            "tipo_evento": tipo_evento,
            "descricao": descricao,
            "responsavel": responsavel,
            "origem": origem,
            "data_evento": agora(),
            "nome_empresa": "Sistema",
            "nome_produto": "",
        }
    )


def atualizar_dados_dos_eventos():
    for event in EVENTS:
        event["nome_empresa"] = "Sistema"
        event["nome_produto"] = ""

        for point in POINTS:
            if event["asset_id"] and point["asset_id"] == event["asset_id"]:
                event["nome_empresa"] = point["nome_empresa"]
                event["nome_produto"] = point["nome_produto"]

            if event["deal_id"] and point["open_deal_id"] == event["deal_id"]:
                event["nome_empresa"] = point["nome_empresa"]
                event["nome_produto"] = point["nome_produto"]


def criar_dados_iniciais():
    POINTS.clear()
    EVENTS.clear()

    clientes_com_revisao_vencida = {3, 7, 11, 15}
    clientes_com_revisao_proxima = {2, 6, 8, 14, 20}

    for index, cliente in enumerate(CLIENTES_VENDIDOS, start=1):
        nome, responsavel_empresa, telefone, endereco, cidade, estado, latitude, longitude = cliente

        produto = PRODUTOS[(index - 1) % len(PRODUTOS)]
        comercial = COMERCIAIS[index % len(COMERCIAIS)]
        engenheiro = ENGENHEIROS[index % len(ENGENHEIROS)]

        data_venda = hoje() - timedelta(days=40 + index * 13)
        data_instalacao = data_venda + timedelta(days=10)

        if index in clientes_com_revisao_vencida:
            data_proxima_revisao = hoje() - timedelta(days=3 + index)
            situacao_campo = "Revisao vencida"
        elif index in clientes_com_revisao_proxima:
            data_proxima_revisao = hoje() + timedelta(days=5 + index)
            situacao_campo = "Revisao agendada"
        else:
            data_proxima_revisao = data_instalacao + timedelta(days=365)
            situacao_campo = "Em operacao"

        dias, status = calcular_status_revisao(data_proxima_revisao.isoformat())

        ponto = {
            "point_type": "sold",
            "asset_id": index,
            "open_deal_id": None,
            "client_id": index,
            "nome_empresa": nome,
            "cnpj": f"{index:02d}.{index:03d}.{index:03d}/0001-{index:02d}",
            "responsavel_empresa": responsavel_empresa,
            "telefone": telefone,
            "endereco": endereco,
            "cidade": cidade,
            "estado": estado,
            "pais": "Brasil",
            "latitude": latitude,
            "longitude": longitude,
            "pipedrive_deal_id": 9000 + index,
            "titulo_negocio": f"Venda {produto} - {nome}",
            "status_negocio": "Ganho",
            "etapa_funil": "Ganho",
            "produto_interesse": produto,
            "probabilidade": 100,
            "previsao_fechamento": None,
            "proxima_atividade": None,
            "valor": valor_venda(index),
            "moeda": "BRL",
            "data_ganho": data_venda.isoformat(),
            "nome_produto": produto,
            "categoria": "Produto LLK",
            "numero_serie": f"LLK-{hoje().year}-{index:04d}",
            "data_venda": data_venda.isoformat(),
            "data_instalacao": data_instalacao.isoformat(),
            "data_proxima_revisao": data_proxima_revisao.isoformat(),
            "situacao_campo": situacao_campo,
            "responsavel_comercial": comercial,
            "responsavel_manutencao": engenheiro,
            "posicao_correia": (
                f"Correia CT-{(index % 6) + 1:02d} | "
                f"{'lado carga' if index % 2 == 0 else 'lado retorno'} | "
                f"{80 + index * 6} m"
            ),
            "criticidade": "Alta" if index in clientes_com_revisao_vencida else "Media",
            "observacao": "Registro ficticio para demonstracao da plataforma.",
            "updated_at": agora(),
            "dias_restantes_revisao": dias,
            "status_revisao": status,
        }

        POINTS.append(ponto)

        registrar_evento(
            asset_id=index,
            open_deal_id=None,
            tipo_evento="Venda importada",
            descricao=f"Negocio ganho no Pipedrive e {produto} criado como produto em campo.",
            responsavel=comercial,
            origem="Pipedrive",
        )

        registrar_evento(
            asset_id=index,
            open_deal_id=None,
            tipo_evento="Instalacao",
            descricao=f"Equipamento instalado em {ponto['posicao_correia']}.",
            responsavel=engenheiro,
            origem="Engenharia",
        )

        if index in clientes_com_revisao_vencida:
            registrar_evento(
                asset_id=index,
                open_deal_id=None,
                tipo_evento="Alerta de revisao",
                descricao="Revisao vencida. Cliente deve ser priorizado.",
                responsavel="Sistema",
                origem="Plataforma",
            )

    for offset, negocio in enumerate(NEGOCIOS_ABERTOS, start=1):
        index = 20 + offset
        nome, responsavel_empresa, telefone, endereco, cidade, estado, latitude, longitude = negocio

        produto = PRODUTOS[(index - 1) % len(PRODUTOS)]
        comercial = COMERCIAIS[index % len(COMERCIAIS)]
        etapa = ETAPAS_ABERTAS[(offset - 1) % len(ETAPAS_ABERTAS)]

        probabilidades = [20, 35, 55, 70, 15, 45, 60, 80]
        probabilidade = probabilidades[offset - 1]

        previsao_fechamento = hoje() + timedelta(days=15 + offset * 9)
        proxima_atividade = hoje() + timedelta(days=(offset % 6) - 2)

        dias_atividade = (proxima_atividade - hoje()).days

        if dias_atividade < 0:
            status_atividade = "Atividade atrasada"
        else:
            status_atividade = "Em acompanhamento"

        ponto = {
            "point_type": "open",
            "asset_id": None,
            "open_deal_id": index,
            "client_id": index,
            "nome_empresa": nome,
            "cnpj": f"{index:02d}.{index:03d}.{index:03d}/0001-{index:02d}",
            "responsavel_empresa": responsavel_empresa,
            "telefone": telefone,
            "endereco": endereco,
            "cidade": cidade,
            "estado": estado,
            "pais": "Brasil",
            "latitude": latitude,
            "longitude": longitude,
            "pipedrive_deal_id": 9000 + index,
            "titulo_negocio": f"Oportunidade {produto} - {nome}",
            "status_negocio": "Aberto",
            "etapa_funil": etapa,
            "produto_interesse": produto,
            "probabilidade": probabilidade,
            "previsao_fechamento": previsao_fechamento.isoformat(),
            "proxima_atividade": proxima_atividade.isoformat(),
            "valor": 45000 + offset * 18000,
            "moeda": "BRL",
            "data_ganho": None,
            "nome_produto": produto,
            "categoria": "Em negociacao",
            "numero_serie": None,
            "data_venda": None,
            "data_instalacao": None,
            "data_proxima_revisao": None,
            "situacao_campo": "Negocio aberto",
            "responsavel_comercial": comercial,
            "responsavel_manutencao": None,
            "posicao_correia": None,
            "criticidade": "Alta" if probabilidade >= 70 else "Media",
            "observacao": "Oportunidade comercial ainda nao vendida.",
            "updated_at": agora(),
            "dias_restantes_revisao": dias_atividade,
            "status_revisao": status_atividade,
        }

        POINTS.append(ponto)

        registrar_evento(
            asset_id=None,
            open_deal_id=index,
            tipo_evento="Oportunidade importada",
            descricao=f"Negocio aberto em etapa {etapa}.",
            responsavel=comercial,
            origem="Pipedrive",
        )

    atualizar_dados_dos_eventos()


def atualizar_status_dos_pontos():
    for point in POINTS:
        if point["point_type"] == "sold":
            dias, status = calcular_status_revisao(point["data_proxima_revisao"])
            point["dias_restantes_revisao"] = dias
            point["status_revisao"] = status
        else:
            if point["proxima_atividade"]:
                data_atividade = date.fromisoformat(point["proxima_atividade"])
                dias = (data_atividade - hoje()).days
            else:
                dias = 99999

            point["dias_restantes_revisao"] = dias

            if dias < 0:
                point["status_revisao"] = "Atividade atrasada"
            else:
                point["status_revisao"] = "Em acompanhamento"


def aplicar_filtros(
    pontos,
    produto="",
    estado="",
    responsavel="",
    status_revisao="",
    situacao="",
    etapa="",
    q="",
):
    atualizar_status_dos_pontos()

    resultado = []

    for point in pontos:
        if produto and point["nome_produto"] != produto:
            continue

        if estado and point["estado"] != estado:
            continue

        if responsavel and point["responsavel_comercial"] != responsavel:
            continue

        if status_revisao and point["status_revisao"] != status_revisao:
            continue

        if situacao and point["situacao_campo"] != situacao:
            continue

        if etapa and point["etapa_funil"] != etapa:
            continue

        if q:
            texto = " ".join(
                str(point.get(key) or "")
                for key in [
                    "nome_empresa",
                    "cidade",
                    "estado",
                    "nome_produto",
                    "produto_interesse",
                    "responsavel_empresa",
                    "numero_serie",
                    "etapa_funil",
                    "responsavel_comercial",
                ]
            ).lower()

            if q.lower() not in texto:
                continue

        resultado.append(point)

    return resultado


def carregar_pontos(
    view="sold",
    produto="",
    estado="",
    responsavel="",
    status_revisao="",
    situacao="",
    etapa="",
    q="",
):
    if view == "sold":
        pontos = [point for point in POINTS if point["point_type"] == "sold"]
    elif view == "open":
        pontos = [point for point in POINTS if point["point_type"] == "open"]
    else:
        pontos = POINTS[:]

    return aplicar_filtros(
        pontos=pontos,
        produto=produto,
        estado=estado,
        responsavel=responsavel,
        status_revisao=status_revisao,
        situacao=situacao,
        etapa=etapa,
        q=q,
    )


criar_dados_iniciais()
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_connections.append(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_connections:
            ws_connections.remove(ws)


@app.get("/api/summary")
def summary():
    atualizar_status_dos_pontos()

    vendidos = [point for point in POINTS if point["point_type"] == "sold"]
    abertos = [point for point in POINTS if point["point_type"] == "open"]

    status_vendidos = [point["status_revisao"] for point in vendidos]

    return {
        "clientes_vendidos": len(set(point["nome_empresa"] for point in vendidos)),
        "produtos_em_campo": len(vendidos),
        "negocios_abertos": len(abertos),
        "valor_aberto": sum(float(point["valor"] or 0) for point in abertos),
        "revisoes_vencidas": status_vendidos.count("Vencida"),
        "revisoes_proximas": status_vendidos.count("Proxima"),
        "estados_atendidos": len(set(point["estado"] for point in POINTS)),
        "ultima_sincronizacao": agora(),
    }


@app.get("/api/options")
def options():
    atualizar_status_dos_pontos()

    produtos = sorted(set(point["nome_produto"] for point in POINTS))
    estados = sorted(set(point["estado"] for point in POINTS))
    responsaveis = sorted(set(point["responsavel_comercial"] for point in POINTS))

    situacoes = sorted(
        set(
            point["situacao_campo"]
            for point in POINTS
            if point["point_type"] == "sold"
        )
    )

    etapas = sorted(
        set(
            point["etapa_funil"]
            for point in POINTS
            if point["point_type"] == "open"
        )
    )

    return {
        "produtos": produtos,
        "estados": estados,
        "responsaveis": responsaveis,
        "situacoes": situacoes,
        "etapas": etapas,
        "status_revisao": [
            "Em dia",
            "Proxima",
            "Vencida",
            "Atividade atrasada",
            "Em acompanhamento",
        ],
    }


@app.get("/api/map-points")
def map_points(
    view: str = "sold",
    produto: str = "",
    estado: str = "",
    responsavel: str = "",
    status_revisao: str = "",
    situacao: str = "",
    etapa: str = "",
    q: str = "",
):
    return carregar_pontos(
        view=view,
        produto=produto,
        estado=estado,
        responsavel=responsavel,
        status_revisao=status_revisao,
        situacao=situacao,
        etapa=etapa,
        q=q,
    )


@app.get("/api/assets")
def list_assets(
    produto: str = "",
    estado: str = "",
    responsavel: str = "",
    status_revisao: str = "",
    situacao: str = "",
    q: str = "",
):
    return carregar_pontos(
        view="sold",
        produto=produto,
        estado=estado,
        responsavel=responsavel,
        status_revisao=status_revisao,
        situacao=situacao,
        q=q,
    )


@app.get("/api/open-deals")
def list_open_deals(
    produto: str = "",
    estado: str = "",
    responsavel: str = "",
    etapa: str = "",
    q: str = "",
):
    return carregar_pontos(
        view="open",
        produto=produto,
        estado=estado,
        responsavel=responsavel,
        etapa=etapa,
        q=q,
    )


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: int):
    for point in POINTS:
        if point["point_type"] == "sold" and point["asset_id"] == asset_id:
            return point

    raise HTTPException(
        status_code=404,
        detail="Produto em campo nao encontrado",
    )


@app.patch("/api/assets/{asset_id}")
async def update_asset(asset_id: int, payload: AssetUpdate):
    point = None

    for item in POINTS:
        if item["point_type"] == "sold" and item["asset_id"] == asset_id:
            point = item
            break

    if not point:
        raise HTTPException(
            status_code=404,
            detail="Produto em campo nao encontrado",
        )

    if payload.situacao_campo is not None:
        point["situacao_campo"] = payload.situacao_campo

    if payload.data_proxima_revisao is not None:
        point["data_proxima_revisao"] = payload.data_proxima_revisao

    if payload.responsavel_manutencao is not None:
        point["responsavel_manutencao"] = payload.responsavel_manutencao

    if payload.observacao is not None:
        point["observacao"] = payload.observacao

    point["updated_at"] = agora()

    dias, status = calcular_status_revisao(point["data_proxima_revisao"])
    point["dias_restantes_revisao"] = dias
    point["status_revisao"] = status

    descricao = payload.observacao or "Atualizacao manual realizada."

    if payload.situacao_campo:
        descricao = f"Situacao alterada para {payload.situacao_campo}. {descricao}"

    registrar_evento(
        asset_id=asset_id,
        open_deal_id=None,
        tipo_evento="Atualizacao manual",
        descricao=descricao,
        responsavel=payload.responsavel_manutencao or "Usuario teste",
        origem="Plataforma",
    )

    atualizar_dados_dos_eventos()

    await broadcast("asset_updated", {"asset_id": asset_id})

    return point


@app.get("/api/assets/{asset_id}/events")
def asset_events(asset_id: int):
    atualizar_dados_dos_eventos()

    eventos_do_ativo = [
        event for event in EVENTS
        if event["asset_id"] == asset_id
    ]

    return sorted(
        eventos_do_ativo,
        key=lambda item: item["data_evento"],
        reverse=True,
    )


@app.post("/api/assets/{asset_id}/events")
async def create_event(asset_id: int, payload: EventCreate):
    exists = any(
        point["point_type"] == "sold" and point["asset_id"] == asset_id
        for point in POINTS
    )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Produto em campo nao encontrado",
        )

    registrar_evento(
        asset_id=asset_id,
        open_deal_id=None,
        tipo_evento=payload.tipo_evento,
        descricao=payload.descricao,
        responsavel=payload.responsavel or "Usuario teste",
        origem="Plataforma",
    )

    atualizar_dados_dos_eventos()

    await broadcast("event_created", {"asset_id": asset_id})

    return {"ok": True}


@app.post("/api/assets/{asset_id}/attachments")
async def upload_attachment(asset_id: int, file: UploadFile = File(...)):
    exists = any(
        point["point_type"] == "sold" and point["asset_id"] == asset_id
        for point in POINTS
    )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Produto em campo nao encontrado",
        )

    safe_name = file.filename.replace("/", "_").replace("\\", "_")

    folder = UPLOAD_DIR / str(asset_id)
    folder.mkdir(parents=True, exist_ok=True)

    target = folder / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"

    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    url = f"/uploads/{asset_id}/{target.name}"

    registrar_evento(
        asset_id=asset_id,
        open_deal_id=None,
        tipo_evento="Arquivo anexado",
        descricao=f"Arquivo anexado: {safe_name}",
        responsavel="Usuario teste",
        origem="Plataforma",
    )

    atualizar_dados_dos_eventos()

    await broadcast("attachment_created", {"asset_id": asset_id})

    return {
        "ok": True,
        "url": url,
    }


@app.get("/api/events")
def events(limit: int = 80):
    atualizar_dados_dos_eventos()

    eventos_ordenados = sorted(
        EVENTS,
        key=lambda item: item["data_evento"],
        reverse=True,
    )

    return eventos_ordenados[:limit]


@app.get("/api/export/kml")
def export_kml(
    view: str = "sold",
    produto: str = "",
    estado: str = "",
    responsavel: str = "",
    status_revisao: str = "",
    situacao: str = "",
    etapa: str = "",
    q: str = "",
):
    pontos = carregar_pontos(
        view=view,
        produto=produto,
        estado=estado,
        responsavel=responsavel,
        status_revisao=status_revisao,
        situacao=situacao,
        etapa=etapa,
        q=q,
    )

    placemarks = []

    for point in pontos:
        titulo = f"{point['nome_empresa']} - {point['nome_produto']}"

        if point["point_type"] == "sold":
            tipo_ponto = "Cliente vendido"
        else:
            tipo_ponto = "Negocio em aberto"

        descricao = f"""
        Tipo: {tipo_ponto}<br/>
        Telefone: {point['telefone']}<br/>
        Responsavel empresa: {point['responsavel_empresa']}<br/>
        Responsavel LLK: {point['responsavel_comercial']}<br/>
        Status: {point['status_revisao']}<br/>
        Produto: {point['nome_produto']}<br/>
        Valor: {point['valor']} {point['moeda']}<br/>
        """

        placemark = f"""
        <Placemark>
          <name>{escape(titulo)}</name>
          <description><![CDATA[{descricao}]]></description>
          <Point>
            <coordinates>{point['longitude']},{point['latitude']},0</coordinates>
          </Point>
        </Placemark>
        """

        placemarks.append(placemark)

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>LLK Field Platform - pontos filtrados</name>
    {''.join(placemarks)}
  </Document>
</kml>
"""

    return Response(
        content=kml,
        media_type="application/vnd.google-earth.kml+xml",
        headers={
            "Content-Disposition": "attachment; filename=llk_pontos_filtrados.kml"
        },
    )


@app.post("/api/pipedrive/sync")
async def pipedrive_sync():
    registrar_evento(
        asset_id=1,
        open_deal_id=None,
        tipo_evento="Sincronizacao Pipedrive",
        descricao=(
            "Sincronizacao mockada executada. "
            "Na versao real, buscar API do Pipedrive."
        ),
        responsavel="Sistema",
        origem="Pipedrive",
    )

    atualizar_dados_dos_eventos()

    await broadcast("pipedrive_sync", {})

    return {
        "ok": True,
        "message": "Sincronizacao mockada executada",
    }


@app.post("/api/webhooks/pipedrive")
async def pipedrive_webhook(request: Request):
    payload = await request.json()

    registrar_evento(
        asset_id=1,
        open_deal_id=None,
        tipo_evento="Webhook Pipedrive",
        descricao=json.dumps(payload, ensure_ascii=False)[:700],
        responsavel="Sistema",
        origem="Pipedrive",
    )

    atualizar_dados_dos_eventos()

    await broadcast(
        "pipedrive_webhook",
        payload if isinstance(payload, dict) else {},
    )

    return {"ok": True}