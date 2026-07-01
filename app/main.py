import os
import sqlite3
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

APP_NAME = os.getenv('APP_NAME', 'LLK Field Platform')
DATABASE_PATH = Path(os.getenv('DATABASE_PATH', './data/llk_field_platform.db'))
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', './app/uploads'))
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ['*'] else ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

STATIC_DIR = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
app.mount('/uploads', StaticFiles(directory=UPLOAD_DIR), name='uploads')

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


def db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_rows(rows):
    return [dict(r) for r in rows]


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def review_status(next_review: Optional[str]):
    if not next_review:
        return 99999, 'Sem data'
    target = date.fromisoformat(next_review)
    days = (target - date.today()).days
    if days < 0:
        return days, 'Vencida'
    if days <= 30:
        return days, 'Proxima'
    return days, 'Em dia'


async def broadcast(event: str, payload: dict | None = None):
    dead = []
    message = {'event': event, 'payload': payload or {}, 'time': now_text()}
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in ws_connections:
            ws_connections.remove(ws)


PRODUCTS = [
    (1001, 'RADEC LLK-100', 'Radec', 365),
    (1002, 'RADEC LLK-300', 'Radec', 365),
    (1003, 'RADEC Guard Pro', 'Radec', 365),
    (1004, 'Sensor de Rasgo RS-20', 'Sensor', 365),
    (1005, 'Painel de Monitoramento PM-900', 'Painel', 365),
]

CLIENTS = [
    ('Alfa Mineracao', '11.111.111/0001-10', 'Carlos Henrique', '(31) 99910-2200', 'Av. Amazonas, 1200', 'Belo Horizonte', 'MG', -19.9167, -43.9345),
    ('Beta Siderurgia', '22.222.222/0001-20', 'Fernanda Duarte', '(11) 98822-4433', 'Rua Funchal, 320', 'Sao Paulo', 'SP', -23.5505, -46.6333),
    ('Gama Energia', '33.333.333/0001-30', 'Rodrigo Alves', '(21) 97740-8811', 'Av. Rio Branco, 45', 'Rio de Janeiro', 'RJ', -22.9068, -43.1729),
    ('Delta Agritech', '44.444.444/0001-40', 'Joao Meireles', '(62) 99660-2100', 'Av. T-9, 880', 'Goiania', 'GO', -16.6869, -49.2648),
    ('Epsilon Alimentos', '55.555.555/0001-50', 'Renata Lopes', '(41) 98800-1199', 'Rua XV de Novembro, 450', 'Curitiba', 'PR', -25.4284, -49.2733),
    ('Zeta Celulose', '66.666.666/0001-60', 'Patricia Nunes', '(71) 98850-3300', 'Av. Tancredo Neves, 120', 'Salvador', 'BA', -12.9777, -38.5016),
    ('Sigma Logistica', '77.777.777/0001-70', 'Marcelo Vieira', '(51) 97788-4411', 'Av. Borges de Medeiros, 880', 'Porto Alegre', 'RS', -30.0346, -51.2177),
    ('Omega Quimica', '88.888.888/0001-80', 'Luciana Ferraz', '(81) 99920-2221', 'Av. Boa Viagem, 1000', 'Recife', 'PE', -8.0476, -34.8770),
    ('Mineracao Serra Azul', '12.120.120/0001-12', 'Andre Sales', '(31) 98450-1001', 'Rodovia MG-050, km 60', 'Itauna', 'MG', -20.0753, -44.5764),
    ('Vale Norte Operacoes', '13.130.130/0001-13', 'Beatriz Paiva', '(94) 98120-4000', 'Estrada Industrial, 450', 'Parauapebas', 'PA', -6.0675, -49.9023),
    ('Carajas Processos', '14.140.140/0001-14', 'Rafael Porto', '(94) 99211-5511', 'Av. Liberdade, 240', 'Maraba', 'PA', -5.3686, -49.1178),
    ('Nordeste Cimentos', '15.150.150/0001-15', 'Camila Rocha', '(85) 98888-7711', 'BR-116, km 18', 'Fortaleza', 'CE', -3.7319, -38.5267),
    ('SulMetal Componentes', '16.160.160/0001-16', 'Eduardo Ramos', '(47) 99930-9090', 'Rua Industrial, 700', 'Joinville', 'SC', -26.3044, -48.8487),
    ('Pantanal Fertilizantes', '17.170.170/0001-17', 'Helena Martins', '(67) 99610-3030', 'Av. Afonso Pena, 900', 'Campo Grande', 'MS', -20.4697, -54.6201),
    ('Bahia Minerios', '18.180.180/0001-18', 'Nicolas Freitas', '(77) 98844-2210', 'Av. Minas Gerais, 150', 'Caetite', 'BA', -14.0696, -42.4755),
    ('Amazonas Graos', '19.190.190/0001-19', 'Paula Menezes', '(92) 99444-1212', 'Av. Djalma Batista, 500', 'Manaus', 'AM', -3.1190, -60.0217),
    ('Centro-Oeste Bioenergia', '20.200.200/0001-20', 'Gustavo Nery', '(65) 99990-7000', 'Av. CPA, 780', 'Cuiaba', 'MT', -15.6014, -56.0979),
    ('Espirito Santo Portos', '21.210.210/0001-21', 'Larissa Fontes', '(27) 98870-3020', 'Av. Jeronimo Monteiro, 330', 'Vitoria', 'ES', -20.3155, -40.3128),
    ('Parana Papel e Celulose', '23.230.230/0001-23', 'Thiago Moura', '(42) 99111-8888', 'Rua das Araucarias, 55', 'Ponta Grossa', 'PR', -25.0994, -50.1583),
    ('Maranhao Graneis', '24.240.240/0001-24', 'Isabela Prado', '(98) 98222-3030', 'Av. dos Holandeses, 880', 'Sao Luis', 'MA', -2.5307, -44.3068),
]


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipedrive_org_id INTEGER UNIQUE,
            nome_empresa TEXT NOT NULL,
            cnpj TEXT,
            responsavel_empresa TEXT,
            telefone TEXT,
            endereco TEXT,
            cidade TEXT,
            estado TEXT,
            pais TEXT DEFAULT 'Brasil',
            latitude REAL,
            longitude REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipedrive_deal_id INTEGER UNIQUE,
            client_id INTEGER NOT NULL,
            titulo TEXT,
            status_negocio TEXT,
            valor REAL,
            moeda TEXT DEFAULT 'BRL',
            responsavel_llk TEXT,
            data_ganho TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipedrive_product_id INTEGER UNIQUE,
            nome_produto TEXT NOT NULL,
            categoria TEXT,
            tempo_revisao_dias INTEGER DEFAULT 365,
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS field_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            deal_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            numero_serie TEXT,
            data_venda TEXT,
            data_instalacao TEXT,
            data_proxima_revisao TEXT,
            situacao_campo TEXT,
            responsavel_comercial TEXT,
            responsavel_manutencao TEXT,
            posicao_correia TEXT,
            criticidade TEXT,
            observacao TEXT,
            ativo INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS maintenance_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            tipo_evento TEXT NOT NULL,
            descricao TEXT,
            responsavel TEXT,
            origem TEXT DEFAULT 'Plataforma',
            data_evento TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            nome_arquivo TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            tipo_arquivo TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        existing = conn.execute('SELECT COUNT(*) AS n FROM clients').fetchone()['n']
        if existing == 0:
            seed(conn)


def seed(conn: sqlite3.Connection):
    for ext_id, name, category, days in PRODUCTS:
        conn.execute('INSERT INTO products (pipedrive_product_id, nome_produto, categoria, tempo_revisao_dias) VALUES (?, ?, ?, ?)', (ext_id, name, category, days))
    comerciais = ['Mariana Costa', 'Bruno Lima', 'Ana Paula', 'Rafael Mendes', 'Diego Torres']
    engenheiros = ['Eng. Lucas', 'Eng. Sofia', 'Eng. Mateus', 'Eng. Helena']
    situacoes = ['Em operacao', 'Revisao agendada', 'Em manutencao', 'Aguardando instalacao', 'Em operacao']
    criticidades = ['Baixa', 'Media', 'Alta', 'Media', 'Baixa']
    for i, client in enumerate(CLIENTS, start=1):
        org_id = 5000 + i
        conn.execute('''INSERT INTO clients (pipedrive_org_id, nome_empresa, cnpj, responsavel_empresa, telefone, endereco, cidade, estado, pais, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Brasil', ?, ?)''', (org_id, *client))
        client_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        product_row = conn.execute('SELECT * FROM products WHERE pipedrive_product_id = ?', (PRODUCTS[(i - 1) % len(PRODUCTS)][0],)).fetchone()
        comercial = comerciais[i % len(comerciais)]
        engenheiro = engenheiros[i % len(engenheiros)]
        won_date = date.today() - timedelta(days=35 + i * 13)
        install_date = won_date + timedelta(days=10 + i % 9)
        next_review = install_date + timedelta(days=365)
        if i in [3, 7, 11, 15]:
            next_review = date.today() - timedelta(days=5 + i)
        elif i in [2, 6, 8, 14, 20]:
            next_review = date.today() + timedelta(days=5 + i)
        conn.execute('''INSERT INTO deals (pipedrive_deal_id, client_id, titulo, status_negocio, valor, moeda, responsavel_llk, data_ganho) VALUES (?, ?, ?, ?, ?, 'BRL', ?, ?)''', (9000 + i, client_id, f'Venda {product_row["nome_produto"]} - {client[0]}', 'Ganho', 38000 + i * 9300, comercial, won_date.isoformat()))
        deal_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        situacao = situacoes[i % len(situacoes)]
        if i in [3, 7, 11, 15]: situacao = 'Revisao vencida'
        elif i in [2, 6, 8, 14, 20]: situacao = 'Revisao agendada'
        posicao = f'Correia CT-{(i % 6) + 1:02d} | {"lado carga" if i % 2 == 0 else "lado retorno"} | {80 + i * 6} m'
        conn.execute('''INSERT INTO field_assets (client_id, deal_id, product_id, numero_serie, data_venda, data_instalacao, data_proxima_revisao, situacao_campo, responsavel_comercial, responsavel_manutencao, posicao_correia, criticidade, observacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (client_id, deal_id, product_row['id'], f'LLK-{date.today().year}-{i:04d}', won_date.isoformat(), install_date.isoformat(), next_review.isoformat(), situacao, comercial, engenheiro, posicao, criticidades[i % len(criticidades)], 'Registro ficticio para demonstracao da plataforma.'))
        asset_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        events = [
            ('Venda importada', f'Negocio ganho no Pipedrive e {product_row["nome_produto"]} criado como produto em campo.', comercial, 'Pipedrive'),
            ('Instalacao', f'Equipamento instalado em {posicao}.', engenheiro, 'Engenharia'),
            ('Inspecao visual', 'Inspecao inicial sem avarias criticas.', engenheiro, 'Plataforma'),
        ]
        if i in [3, 7, 11, 15]: events.append(('Alerta de revisao', 'Revisao vencida. Cliente deve ser priorizado.', 'Sistema', 'Plataforma'))
        elif i in [2, 6, 8, 14, 20]: events.append(('Revisao agendada', 'Revisao dentro dos proximos 30 dias.', engenheiro, 'Plataforma'))
        for tipo, desc, resp, origem in events:
            conn.execute('INSERT INTO maintenance_events (asset_id, tipo_evento, descricao, responsavel, origem) VALUES (?, ?, ?, ?, ?)', (asset_id, tipo, desc, resp, origem))

@app.on_event('startup')
def on_startup(): init_db()

@app.get('/')
def index(): return FileResponse(STATIC_DIR / 'index.html')

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept(); ws_connections.append(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_connections: ws_connections.remove(ws)

def base_assets_query():
    return '''SELECT fa.id AS asset_id, c.id AS client_id, c.nome_empresa, c.cnpj, c.responsavel_empresa, c.telefone, c.endereco, c.cidade, c.estado, c.pais, c.latitude, c.longitude, d.pipedrive_deal_id, d.titulo AS titulo_negocio, d.status_negocio, d.valor, d.moeda, d.data_ganho, p.nome_produto, p.categoria, fa.numero_serie, fa.data_venda, fa.data_instalacao, fa.data_proxima_revisao, fa.situacao_campo, fa.responsavel_comercial, fa.responsavel_manutencao, fa.posicao_correia, fa.criticidade, fa.observacao, fa.updated_at FROM field_assets fa JOIN clients c ON c.id = fa.client_id JOIN deals d ON d.id = fa.deal_id JOIN products p ON p.id = fa.product_id WHERE fa.ativo = 1'''

@app.get('/api/summary')
def summary():
    with db() as conn: rows = dict_rows(conn.execute(base_assets_query()).fetchall())
    statuses = [review_status(r['data_proxima_revisao'])[1] for r in rows]
    return {'clientes_ativos': len(set(r['nome_empresa'] for r in rows)), 'produtos_em_campo': len(rows), 'revisoes_vencidas': statuses.count('Vencida'), 'revisoes_proximas': statuses.count('Proxima'), 'estados_atendidos': len(set(r['estado'] for r in rows)), 'ultima_sincronizacao': now_text()}

@app.get('/api/options')
def options():
    with db() as conn:
        products = [r['nome_produto'] for r in conn.execute('SELECT DISTINCT nome_produto FROM products ORDER BY nome_produto').fetchall()]
        estados = [r['estado'] for r in conn.execute('SELECT DISTINCT estado FROM clients ORDER BY estado').fetchall()]
        responsaveis = [r['responsavel_comercial'] for r in conn.execute('SELECT DISTINCT responsavel_comercial FROM field_assets ORDER BY responsavel_comercial').fetchall()]
        situacoes = [r['situacao_campo'] for r in conn.execute('SELECT DISTINCT situacao_campo FROM field_assets ORDER BY situacao_campo').fetchall()]
    return {'produtos': products, 'estados': estados, 'responsaveis': responsaveis, 'situacoes': situacoes, 'status_revisao': ['Em dia', 'Proxima', 'Vencida']}

@app.get('/api/assets')
def list_assets(produto: str = '', estado: str = '', responsavel: str = '', status_revisao: str = '', situacao: str = '', q: str = ''):
    sql = base_assets_query(); params = []
    if produto: sql += ' AND p.nome_produto = ?'; params.append(produto)
    if estado: sql += ' AND c.estado = ?'; params.append(estado)
    if responsavel: sql += ' AND fa.responsavel_comercial = ?'; params.append(responsavel)
    if situacao: sql += ' AND fa.situacao_campo = ?'; params.append(situacao)
    if q:
        sql += ' AND (c.nome_empresa LIKE ? OR c.cidade LIKE ? OR p.nome_produto LIKE ? OR c.responsavel_empresa LIKE ? OR fa.numero_serie LIKE ?)'
        like = f'%{q}%'; params.extend([like, like, like, like, like])
    sql += ' ORDER BY c.nome_empresa ASC'
    with db() as conn: rows = dict_rows(conn.execute(sql, params).fetchall())
    result = []
    for r in rows:
        days, status = review_status(r['data_proxima_revisao'])
        if status_revisao and status != status_revisao: continue
        r['dias_restantes_revisao'] = days; r['status_revisao'] = status; result.append(r)
    return result

@app.get('/api/assets/{asset_id}')
def get_asset(asset_id: int):
    for item in list_assets():
        if item['asset_id'] == asset_id: return item
    raise HTTPException(status_code=404, detail='Produto em campo nao encontrado')

@app.patch('/api/assets/{asset_id}')
async def update_asset(asset_id: int, payload: AssetUpdate):
    updates = []; params = []
    for field in ['situacao_campo', 'data_proxima_revisao', 'responsavel_manutencao', 'observacao']:
        value = getattr(payload, field)
        if value is not None: updates.append(f'{field} = ?'); params.append(value)
    updates.append('updated_at = CURRENT_TIMESTAMP'); params.append(asset_id)
    with db() as conn:
        cur = conn.execute(f'UPDATE field_assets SET {", ".join(updates)} WHERE id = ?', params)
        if cur.rowcount == 0: raise HTTPException(status_code=404, detail='Produto em campo nao encontrado')
        desc = payload.observacao or 'Atualizacao manual realizada.'
        if payload.situacao_campo: desc = f'Situacao alterada para {payload.situacao_campo}. {desc}'
        conn.execute('INSERT INTO maintenance_events (asset_id, tipo_evento, descricao, responsavel, origem) VALUES (?, ?, ?, ?, ?)', (asset_id, 'Atualizacao manual', desc, payload.responsavel_manutencao or 'Usuario teste', 'Plataforma'))
    await broadcast('asset_updated', {'asset_id': asset_id}); return get_asset(asset_id)

@app.get('/api/assets/{asset_id}/events')
def asset_events(asset_id: int):
    with db() as conn: rows = dict_rows(conn.execute('SELECT * FROM maintenance_events WHERE asset_id = ? ORDER BY data_evento DESC', (asset_id,)).fetchall())
    return rows

@app.post('/api/assets/{asset_id}/events')
async def create_event(asset_id: int, payload: EventCreate):
    with db() as conn:
        exists = conn.execute('SELECT id FROM field_assets WHERE id = ?', (asset_id,)).fetchone()
        if not exists: raise HTTPException(status_code=404, detail='Produto em campo nao encontrado')
        conn.execute('INSERT INTO maintenance_events (asset_id, tipo_evento, descricao, responsavel, origem) VALUES (?, ?, ?, ?, ?)', (asset_id, payload.tipo_evento, payload.descricao, payload.responsavel or 'Usuario teste', 'Plataforma'))
    await broadcast('event_created', {'asset_id': asset_id}); return {'ok': True}

@app.post('/api/assets/{asset_id}/attachments')
async def upload_attachment(asset_id: int, file: UploadFile = File(...)):
    safe = file.filename.replace('/', '_').replace('\\', '_')
    folder = UPLOAD_DIR / str(asset_id); folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{safe}'
    with target.open('wb') as out: shutil.copyfileobj(file.file, out)
    url = f'/uploads/{asset_id}/{target.name}'
    with db() as conn:
        exists = conn.execute('SELECT id FROM field_assets WHERE id = ?', (asset_id,)).fetchone()
        if not exists: raise HTTPException(status_code=404, detail='Produto em campo nao encontrado')
        conn.execute('INSERT INTO attachments (asset_id, nome_arquivo, caminho_arquivo, tipo_arquivo) VALUES (?, ?, ?, ?)', (asset_id, safe, url, file.content_type))
        conn.execute('INSERT INTO maintenance_events (asset_id, tipo_evento, descricao, responsavel, origem) VALUES (?, ?, ?, ?, ?)', (asset_id, 'Arquivo anexado', f'Arquivo anexado: {safe}', 'Usuario teste', 'Plataforma'))
    await broadcast('attachment_created', {'asset_id': asset_id}); return {'ok': True, 'url': url}

@app.get('/api/events')
def events(limit: int = 80):
    with db() as conn:
        rows = dict_rows(conn.execute('''SELECT me.*, c.nome_empresa, p.nome_produto FROM maintenance_events me JOIN field_assets fa ON fa.id = me.asset_id JOIN clients c ON c.id = fa.client_id JOIN products p ON p.id = fa.product_id ORDER BY me.data_evento DESC LIMIT ?''', (limit,)).fetchall())
    return rows

@app.post('/api/pipedrive/sync')
async def pipedrive_sync():
    with db() as conn:
        first = conn.execute('SELECT id FROM field_assets LIMIT 1').fetchone()
        if first: conn.execute('INSERT INTO maintenance_events (asset_id, tipo_evento, descricao, responsavel, origem) VALUES (?, ?, ?, ?, ?)', (first['id'], 'Sincronizacao Pipedrive', 'Sincronizacao mockada executada. Na versao real, buscar API do Pipedrive.', 'Sistema', 'Pipedrive'))
    await broadcast('pipedrive_sync', {}); return {'ok': True, 'message': 'Sincronizacao mockada executada'}

@app.post('/api/webhooks/pipedrive')
async def pipedrive_webhook(request: Request):
    payload = await request.json()
    with db() as conn:
        first = conn.execute('SELECT id FROM field_assets LIMIT 1').fetchone()
        if first: conn.execute('INSERT INTO maintenance_events (asset_id, tipo_evento, descricao, responsavel, origem) VALUES (?, ?, ?, ?, ?)', (first['id'], 'Webhook Pipedrive', json.dumps(payload, ensure_ascii=False)[:700], 'Sistema', 'Pipedrive'))
    await broadcast('pipedrive_webhook', payload if isinstance(payload, dict) else {}); return {'ok': True}
