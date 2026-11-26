# PropSec — prospecção de influenciadoras

## A operação
Buscamos influenciadoras **de menor porte** no Instagram para parcerias:
- **Volume é o que importa**: quase toda "blogueira" compatível é oportunidade. O critério
  principal é o **estilo** (parecer com as fechadas) + faixa de seguidores.
- Seguidores: ideal **3.500 a 15.000**; vale de ~1.000 a 30.000 (15–30k só com estilo forte).
  **Acima de 30.000 não trazer**: o usuário não gosta de fechar com perfis grandes.
- **Perfil comercial derruba a nota**: stories tomados por divulgação de várias lojas/marcas
  (sapato, perfume, roupa da cidade) ou dona de negócio com muitas clientes → raramente fecha.
  Escrever "publi" na bio não é problema. Empreendedora com poucas clientes ainda pode fechar.
- O agente **assiste os stories do dia** (só assistir, nunca reagir/responder) e registra
  `stories_qtd` e `stories_publi` (fração de divulgação). A conta aparece em "quem viu".
- Views de reels/engajamento são bônus, não requisito. Poucos posts no feed é normal.
- Blogueira de comunidade/"baixa renda", foto simples de celular: **não** é ponto negativo —
  público fiel, já deu lucro alto. Não premiar "produção bonita".
- Antes de prospectar: `python propsec.py exemplos` (gosto real do usuário: fechadas, aprovadas,
  descartadas). O sistema reaprende sozinho a cada 5 decisões dele no painel.
- Prospecção **aberta**: muitas "pagam de blogueira" — público pequeno mas ativo, conhecida na
  cidade/região, interage, às vezes já faz outras parcerias. Forte no **Maranhão** (cidades do
  interior incluídas), mas não só.
- Públicos específicos (mãe solo, mulher de preso, maternidade etc.) são **etiquetas**, não
  filtros. Não restringir a busca a eles.
- Recusar ou não responder **não** torna um perfil ruim. Perfis bons que recusaram são
  referência do tipo `gostamos`.

## Resultado = lucro por dia
O que define uma parceria boa é o **lucro no dia** que ela gera. Referências (15 fechadas, em
`referencias/referencias_iniciais.json`): `alto` = mais de R$ 1.000 em um dia (gauannelacerda,
tamillymacedo_, samara_reggina_, lay_ruivinha288); `medio` = R$ 200–500/dia (as outras 11).
Registrar sempre o lucro (`--lucro`) ou o nível (`--resultado`) das novas parcerias: é o rótulo
mais forte do aprendizado. Perfis "não tão bons" no papel já deram resultado alto.

## Como achar perfis
- Caminho principal: **sugestões do Instagram (perfis semelhantes) a partir de perfis bons**
  — fechadas, aprovadas pelo usuário, referências — e depois bola de neve a partir dos achados
  novos bons. `python propsec.py proximas-fontes` lista as sementes.
- **Não** usar a lista "seguindo" de agências (fly.creators.br, hub.influ.br): já são agenciadas.
- Complemento (≤ 1/3): aba **Marcados** de lojas locais de moda/beleza (boa fonte de "blogueira
  da cidade"), cidades e hashtags. Lojas sem público feminino (móveis, mercado) não servem.
- O usuário chama perfis por fora; quando ele mandar uma lista, registre com
  `python propsec.py contatados @a @b ...` (ou `--arquivo lista.txt`).
- Perfis que o usuário **aprova** na fila viram sementes e ensinam o sistema — mas **não
  afunilar**: cada sessão é ~50% linha aprovada, ~20% potencial novo, ~30% exploração
  (cidades do interior, lojas/Marcados, hashtags, estilos diferentes com público real).

## Regras do agente
- No Instagram **só leitura**: nunca enviar mensagem, seguir, curtir, comentar, reagir.
  As mensagens são enviadas pela equipe, fora do agente.
- Conta exclusiva de prospecção. **Antes de abrir cada perfil: `python propsec.py liberar @x`**
  (timeout 10 min). `PARAR` → encerrar a sessão. Navegar clicando e rolando, como pessoa.
- Qualquer bloqueio/captcha/aviso do Instagram → `python propsec.py alerta "..."`, parar e avisar.
- Limites e botão PARAR: http://localhost:8000/seguranca (o usuário controla).
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
