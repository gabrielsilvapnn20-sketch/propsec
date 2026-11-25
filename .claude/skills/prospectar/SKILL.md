---
name: prospectar
description: Rodar uma sessão de prospecção de influenciadoras no Instagram pelo Claude in Chrome — encontrar perfis seguindo as sugestões a partir de perfis bons, analisar e salvar no PropSec. Use quando o usuário pedir para prospectar, buscar perfis, achar influenciadoras ou rodar o agente.
---

# Sessão de prospecção

Você navega no Instagram com a conta de prospecção (já logada no Chrome) e salva perfis no
PropSec. **Só leitura:** nunca envie mensagem, siga, curta, comente, reaja ou responda story.
Antes de usar o navegador, carregue a skill `anthropic-skills:chrome-browser`.
Trabalhe numa aba nova do Chrome; não mexa nas outras abas.

## Regras de segurança (obrigatórias)

1. **Antes de abrir CADA perfil**, rode o porteiro com timeout de 10 minutos
   (`timeout: 600000` na ferramenta Bash), porque ele pode esperar alguns minutos:
   ```bash
   python propsec.py liberar @perfil
   ```
   `LIBERADO` → pode abrir. `PARAR: ...` → encerre a sessão (passo 5) e diga o motivo ao
   usuário. Não contorne, não espere por conta própria, não abra "só mais um".
2. Qualquer sinal de alerta do Instagram (login/verificação, captcha, "tente mais tarde",
   "ação bloqueada", "atividade incomum", deslogou, páginas que não carregam) →
   `python propsec.py alerta "o que apareceu"`, encerre e avise o usuário.
3. Se o usuário pediu N perfis, pare em N.

## 1. Abrir a sessão

```bash
python propsec.py sessao inicio
python propsec.py proximas-fontes
```
Se `sessao inicio` disser BLOQUEADO, não comece: diga o motivo.

**Tamanho da conversa:** cada perfil analisado enche a memória da conversa (capturas de tela,
textos), e a conversa fica cada vez mais lenta. Faça no máximo ~20 perfis por conversa. Ao
terminar, diga ao usuário para abrir uma **conversa nova** para a próxima sessão.

**Comandos:** use sempre `python propsec.py ...` sozinho, sem `echo ... |`, `&&` ou `cd`
na frente, para que um único padrão de permissão cubra todos.

## 2. Caminho principal: sugestões a partir de perfis bons

O usuário quer **perfis parecidos com os que já deram certo**, achados pelas sugestões do
próprio Instagram. `proximas-fontes` lista as **sementes** (fechadas, aprovadas, referências).

1. Abra uma semente. Ao lado de "Enviar mensagem" há o botão de **perfis semelhantes**
   (ícone de pessoa com "+"). Clique: aparece a faixa de sugestões. Role a faixa para ver mais.
2. Anote os @ das sugestões que parecem mulheres/influenciadoras (pule lojas, páginas,
   homens, famosas grandes).
3. Verifique em lote quais são novos: `python propsec.py existe @a @b @c ...`
   (pule `JA_EXISTE`: já estão no sistema ou já foram contatadas pelo usuário).
4. Analise as novas (passo 3).
5. **Bola de neve:** quando uma nova for boa (nota ≥ 60), use-a como semente também e abra as
   sugestões dela. Assim você sai da rede conhecida.
6. Registre cada semente usada: `python propsec.py fonte sugestoes "<@semente>" --vistos N`.
   Salve os perfis com `"origem": "sugestoes", "origem_detalhe": "<@semente>"`.

**Não use agências** (fly.creators.br, hub.influ.br e parecidas) como fonte: quem elas
seguem já é agenciado. Se um perfil mostrar "Seguido(a) por" uma agência, anote isso nas
observações ("possivelmente agenciada"), mas pode salvar.

**Complemento (no máximo 1/3 da sessão):**
- **Lojas locais de moda/beleza** (boutiques, calçados, salões, cosméticos de cidades
  pequenas): abra a aba **Marcados** da loja. Quem aparece ali fazendo provador/recebidos
  costuma ser exatamente a "blogueira da cidade" que fecha permuta. Ache a loja pela busca
  ("boutique Codó", "loja feminina Bacabal") e registre: `fonte pagina_local "<@loja>" --nota "cidade"`.
  Lojas sem público feminino (móveis, mercado, farmácia grande) não servem.
- Cidades e hashtags do bloco 2 de `proximas-fontes`, principalmente quando as sugestões
  começarem a repetir perfis já vistos.

## 3. Analisar um perfil — modo volume

O nicho vive de **volume**: quase toda "blogueira" compatível é oportunidade. O que decide é
o **estilo** (parecer com as fechadas) e a **faixa de seguidores**. Reels bombando é bônus,
não requisito. Meta: decidir em **30–60 s** por perfil, sem travar em detalhes.

**Passo único (obrigatório):** `liberar` → abrir o perfil → ler o topo (seguidores, nome,
bio, categoria, destaques) → rolar a grade uma ou duas vezes. Se a aba **Reels** estiver a um
clique, abra e anote a mediana das views que aparecem na grade (opcional). Não abra posts
um por um, a não ser que esteja em dúvida.

**Nota de estilo (`estilo_blogueira`, 0 a 1)** — compare com as fechadas:
- **1.0** — igual às fechadas: mulher, selfies/looks/rotina, se apresenta como blogueira/
  criadora ou "parcerias no direct", stories/destaques ativos, cara de conhecida na cidade.
- **0.7** — perfil pessoal ativo de mulher, fotos produzidas, "paga de blogueira", mas sem
  falar em parceria.
- **0.4** — perfil pessoal comum, poucos sinais de blogueira.
- **0–0.2** — não é o estilo: loja, página, homem, empresa, perfil abandonado, famosa grande.

**Salvar como `novo`** se estilo ≥ 0.6 **e** seguidores ≥ 1.000 (ideal 3.500+; acima de
20.000 também vale se o estilo for 0.8+). Caso contrário, salve como `ignorado` com o motivo
(para não revisitar). Seguidores comprados (milhares de seguidores, curtidas/views ínfimas,
comentários de bot) → `ignorado`.

Colete o que estiver **visível sem esforço**: `seguidores`, `seguindo`, `posts`, `nome`,
`bio`, `cidade`/`uf`, `estilo_blogueira`, `stories_ativos` (anel colorido ou destaques
recentes), `faz_publi` (publi/recebidos/lojas marcadas visíveis), `contato`, `link_bio`,
`publicos` (mãe, maternidade, mulher de preso, moda, beleza, humor, forró, praia,
lifestyle, interior...), `media_views_reels` se viu, e `observacoes` com 1 frase de por que
lembra as fechadas. Campo que você não viu: **omita**.

```bash
python propsec.py salvar - <<'JSON'
{"username": "maria.blog", "nome": "Maria", "cidade": "Codó", "uf": "MA",
 "seguidores": 6200, "seguindo": 900, "posts": 41, "estilo_blogueira": 0.9,
 "stories_ativos": 1, "faz_publi": 1, "bio": "...", "publicos": ["mãe", "moda"],
 "media_views_reels": 4800,
 "observacoes": "mãe, looks e provador de loja local, parcerias no direct",
 "origem": "sugestoes", "origem_detalhe": "joicimara"}
JSON
```

Se o usuário pedir **modo detalhado**, além disso abra 2–3 posts/reels e colete
`media_curtidas`, `media_comentarios` e `comentarios_reais` (0 a 1).

**O que as fechadas têm em comum** (`referencias/referencias_iniciais.json`): categoria
"Blogueiro(a)"/"Criador de conteúdo digital", "parcerias no direct", muitas são **mães**,
**poucos posts no feed é normal** (6–31 posts deram resultado), stories ativos, seguem muita
gente, selfies/looks/praia, reels de POV com frase, humor do dia a dia, forró; Nordeste/Norte
e cidades pequenas. Perfis "não tão bons no papel" já deram resultado alto.

## 4. Navegar como uma pessoa

- Chegue nos perfis **clicando** (sugestões, busca), não digitando `instagram.com/usuario`
  em sequência.
- Role aos poucos; não pule direto para o fim. Varie a ordem dos passos.
- De vez em quando (1 a cada 6–8 perfis), volte para o feed ou Explorar por alguns segundos.
- Um perfil por vez, uma aba só. O ritmo entre perfis é do porteiro.

## 5. Encerrar

```bash
python propsec.py fonte sugestoes "<@semente>" --vistos <n>     # para cada semente usada
python propsec.py sessao fim --visitados <total> --salvos <salvos sem ignorados>
python propsec.py resumo
```
Responda ao usuário: quantos perfis viu, quantos bons salvou, os 5 melhores (@, cidade,
seguidores, views médias dos reels, por que vale) e quais sementes renderam mais.
A fila para aprovar fica em http://localhost:8000/fila.
