# LLK Field Platform - MVP executavel

Este pacote cria uma plataforma web de teste para centralizar clientes, negocios, produtos em campo, revisoes, manutencoes e mapa.

Ela segue a arquitetura da opcao 2 discutida:

```text
Pipedrive / outras fontes
-> webhooks/API
-> backend proprio
-> banco de dados
-> plataforma web
-> mapa interativo
-> Power BI opcional para indicadores
```

## O que vem pronto

- Backend em FastAPI.
- Banco SQLite local.
- Seed automatico com 20 clientes ficticios simulando dados do Pipedrive.
- Frontend web responsivo.
- Mapa com Leaflet + OpenStreetMap.
- Filtros por produto, estado, responsavel LLK, status de revisao, situacao em campo e busca.
- Ficha lateral do cliente/equipamento.
- Tabela de equipamentos em campo.
- Historico de manutencao e eventos.
- Atualizacao de status, proxima revisao, responsavel de manutencao e observacao.
- Upload simples de foto/arquivo.
- WebSocket para atualizar a tela quando houver mudanca.
- Endpoint mockado de sincronizacao Pipedrive.
- Endpoint de webhook Pipedrive para versao futura.

## Como rodar no Windows

1. Extraia o ZIP.
2. Abra o terminal dentro da pasta extraida.
3. Rode:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

4. Abra no navegador:

```text
http://127.0.0.1:8000
```

## Como rodar no Linux/Mac

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Depois abra:

```text
http://127.0.0.1:8000
```

## Credenciais

Este MVP nao tem login. Nao coloque em producao sem autenticacao, HTTPS, autorizacao por perfil, auditoria e politicas de backup.

## Dados ficticios

A primeira execucao cria automaticamente 20 clientes ficticios com empresa cliente, responsavel, telefone, negocio ganho, produto vendido, equipamento em campo, posicao na correia, proxima revisao e historico.

## Endpoints principais

```text
GET    /api/summary
GET    /api/assets
GET    /api/assets/{asset_id}
PATCH  /api/assets/{asset_id}
GET    /api/assets/{asset_id}/events
POST   /api/assets/{asset_id}/events
POST   /api/assets/{asset_id}/attachments
GET    /api/events
POST   /api/pipedrive/sync
POST   /api/webhooks/pipedrive
WS     /ws
```

## Proximos passos para producao

1. Trocar SQLite por PostgreSQL/Supabase.
2. Criar login corporativo.
3. Criar permissoes por perfil: Admin, Gestor, Comercial, Engenharia, Leitura.
4. Conectar API real do Pipedrive.
5. Configurar webhooks reais do Pipedrive.
6. Armazenar anexos em SharePoint, Azure Blob ou S3.
7. Criar logs de auditoria.
8. Criar backup automatico.
9. Hospedar em Azure, Render, Railway, VPS ou ambiente interno.
10. Conectar Power BI ao banco para relatorios gerenciais.
