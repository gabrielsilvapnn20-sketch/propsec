# PropSec — prospecção de influenciadoras

## A operação
Buscamos influenciadoras **de menor porte** no Instagram para parcerias:
- Faixa principal: **1.500 a 10.000 seguidores**. Casos especiais: até 15.000–20.000.
- O que mais importa: **views nos stories**. Ninguém de fora vê isso, então usamos sinais
  públicos que andam junto: views dos reels ÷ seguidores, engajamento, comentários de gente
  real, constância, stories ativos.
- Prospecção **aberta**: muitas "pagam de blogueira" — público pequeno mas ativo, conhecida na
  cidade/região, interage, às vezes já faz outras parcerias. Forte no **Maranhão** (cidades do
  interior incluídas), mas não só.
- Públicos específicos (mãe solo, mulher de preso, maternidade etc.) são **etiquetas**, não
  filtros. Não restringir a busca a eles.
- Recusar ou não responder **não** torna um perfil ruim. Perfis bons que recusaram são
  referência do tipo `gostamos`.

## Regras do agente
- No Instagram **só leitura**: nunca enviar mensagem, seguir, curtir, comentar, reagir.
  As mensagens são enviadas pela equipe, fora do agente.
- Conta exclusiva de prospecção. Ritmo humano e limite diário (ver skill `prospectar`).
  Qualquer bloqueio/captcha/aviso → parar e avisar.
- Não inventar números. Campo não visto = omitir.
- Guardar só dados públicos e profissionais do perfil.

## O sistema
- `propsec.py` — linha de comando (salvar, existe, fonte, proximas-fontes, status, recalibrar...).
- `app/` — banco SQLite (`dados/propsec.db`), nota (`scoring.py`), aprendizado
  (`aprendizado.py`) e painel web (`web.py`, http://localhost:8000).
- Funil: novo → aprovado/descartado → contatado → respondeu → negociando → fechado
  (ou recusou / sem_resposta). `ignorado` = o agente viu e não serve (não entra no aprendizado).

## Skills
- `prospectar` — sessão de busca no Instagram via Claude in Chrome.
- `cadastrar-referencias` — prints/perfis já fechados ou que gostamos.
- `recalibrar` — relatório e reajuste dos pesos.

Use `python` (no Windows pode ser `py`). Rode os comandos a partir da pasta do projeto.
