# PropSec

Sistema de prospecção de influenciadoras de menor porte no Instagram: um agente (Claude no
desktop + extensão Claude in Chrome) encontra e analisa perfis, um banco local guarda tudo,
um painel organiza o funil de contato e o sistema aprende com respostas, fechamentos e
views reais dos stories.

## Instalar (uma vez)

1. Instale o **Python 3.11+** (python.org — no Windows marque "Add Python to PATH").
2. Baixe este repositório (git clone ou "Download ZIP").
3. **Windows:** dê dois cliques em `iniciar.bat`. **Mac/Linux:** `./iniciar.sh`.

O painel abre em http://localhost:8000. O banco fica em `dados/propsec.db` (não vai para o
GitHub; faça backup da pasta `dados/`).

> Para o agente usar os comandos `python propsec.py ...`, abra o Claude desktop (Claude Code)
> **nesta pasta**. Se o Windows reclamar de módulo faltando, rode uma vez:
> `pip install -r requirements.txt`.

## Uso no dia a dia

1. **Referências (primeiro passo):** mande ao Claude os prints/@ das parcerias fechadas e dos
   perfis que vocês gostaram (mesmo que tenham recusado). Ele usa a skill
   `cadastrar-referencias`. Prints podem ir em `referencias/prints/`.
2. **Prospectar:** peça "rode uma sessão de prospecção" (skill `prospectar`). O agente navega
   no Instagram só lendo, respeita limite diário e salva os perfis com nota de 0 a 100,
   estimativa de views nos stories e o motivo da nota.
3. **Fila de aprovação** (`/fila`): aprovar ou descartar.
4. **Pipeline** (`/pipeline`): a equipe envia as mensagens e move cada perfil:
   contatado → respondeu → negociando → fechado / recusou / sem resposta.
5. **Views reais:** quando ela mandar print dos stories, registre em "Views reais nos stories"
   no perfil. Dê também a sua nota (1–5) do perfil quando quiser.
6. **Aprendizado** (`/aprendizado`): veja quais sinais e fontes funcionam e aplique a
   recalibração. Ou peça ao Claude "recalibre e me dá um relatório".

## Como a nota funciona

| Sinal | O que mede |
|---|---|
| Alcance dos reels | mediana de views dos reels ÷ seguidores (melhor indicador de stories) |
| Engajamento | (curtidas + comentários) ÷ seguidores |
| Comentários reais | volume e autenticidade dos comentários |
| Stories ativos | posta stories com frequência |
| Constância | posts por semana |
| Perfil de blogueira | já faz publi, marca lojas, contato na bio |
| Faixa de seguidores | 1.500–10.000 ideal; até 20.000 com desconto |
| Região | UF prioritária (MA por padrão) |

Penalidades: suspeita de seguidores comprados e perfil fora da faixa. Sinais não medidos
valem um pouco abaixo da média. Os pesos se ajustam pelos resultados; "recusou" e "sem
resposta" **não** contam como perfil ruim.

## Linha de comando

```
python propsec.py resumo
python propsec.py proximas-fontes
python propsec.py status @fulana fechado --views 1500
python propsec.py recalibrar --simular
python propsec.py exportar perfis.csv
```

API local: `POST /api/perfis` (JSON igual ao do `salvar`), `GET /api/perfis/{username}`,
`GET /exportar.csv`.
