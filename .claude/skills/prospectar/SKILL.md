---
name: prospectar
description: Rodar uma sessão de prospecção de influenciadoras no Instagram pelo Claude in Chrome — encontrar perfis, coletar os sinais públicos e salvar no PropSec. Use quando o usuário pedir para prospectar, buscar perfis, achar influenciadoras ou rodar o agente.
---

# Sessão de prospecção

Você navega no Instagram com a conta de prospecção (já logada no Chrome) e salva perfis no
PropSec. **Você só lê.** Nunca envia mensagem, segue, curte, comenta, responde story ou
clica em "seguir".

## Regras de segurança (obrigatórias)

1. **Antes de abrir CADA perfil**, rode o porteiro, sempre com timeout de 10 minutos
   (parâmetro `timeout: 600000` na ferramenta Bash), porque ele pode esperar alguns minutos:
   ```bash
   python propsec.py liberar @perfil
   ```
   - `LIBERADO ...` → pode abrir o perfil (o porteiro já esperou o intervalo seguro).
   - `PARAR: ...` → **encerre a sessão na hora** (passo 5) e conte ao usuário o motivo.
     Não tente contornar, não espere por conta própria, não abra "só mais um".
2. Se o Instagram mostrar **qualquer** sinal de alerta — pedido de login ou verificação,
   captcha, "tente novamente mais tarde", "ação bloqueada", "atividade incomum", página que
   não carrega repetidamente, deslogou sozinho — rode imediatamente:
   ```bash
   python propsec.py alerta "o que apareceu na tela"
   ```
   Isso pausa o agente por 24 h. Encerre a sessão e avise o usuário.
3. Os limites (por sessão, hora, dia, horário) e o botão PARAR ficam em
   http://localhost:8000/seguranca. Quem decide é o usuário; você só obedece o porteiro.
   Se o usuário pedir N perfis, pare em N mesmo que o porteiro ainda libere.

## Navegar como uma pessoa

O Instagram percebe robô pelo **padrão**, não pela aparência. Por isso:
- **Chegue nos perfis clicando**, como uma pessoa: pela busca, pela lista "seguindo" da
  agência, pelos comentários, pelos perfis marcados. **Evite digitar o endereço
  `instagram.com/usuario` direto** em sequência. Use link direto só de vez em quando.
- **Role a página aos poucos** (várias roladas curtas, não pular para o fim). Olhe o grid,
  abra a aba Reels, role de novo. Abra 2–4 posts, leia, feche.
- Às vezes (1 a cada 5–8 perfis) faça algo "à toa": volte para a lista, role o feed ou o
  Explorar por alguns segundos, abra um destaque e saia.
- Não siga sempre a mesma ordem de passos em todos os perfis.
- Um perfil por vez, uma aba só. Não abra várias abas em paralelo.

Antes de usar o navegador, carregue a skill `anthropic-skills:chrome-browser`.
Trabalhe numa aba nova; não mexa nas abas do usuário.

## 1. Abrir a sessão

```bash
python propsec.py sessao inicio
python propsec.py proximas-fontes
```

Se o usuário pediu uma quantidade ou uma fonte específica, siga o pedido.

`sessao inicio` também diz se o porteiro está liberado. Se aparecer BLOQUEADO, não comece:
diga o motivo ao usuário.

Escolha 2 a 4 fontes da lista. Prefira misturar: 1 "similar" de um perfil que deu certo
(costuma render mais), 1 com bom rendimento e 1 nunca explorada.

## 2. Onde procurar, por tipo de fonte

- **agencia @x** (prioridade máxima): agências/hubs de influenciadoras como `fly.creators.br`
  e `hub.influ.br` seguem várias das parcerias que deram resultado. Abra a lista
  **"seguindo"** da agência e avalie cada mulher dali. Quando achar outra agência/hub
  parecida (aparece no "Seguido(a) por" de várias boas), registre-a:
  `python propsec.py fonte agencia "<@>" --nota "segue X e Y"`.
- **similar @x**: abra o perfil de referência. Use os perfis sugeridos ("Sugestões para
  você" / seta ao lado de Seguir), a lista de quem ela segue, e principalmente **quem comenta
  nos posts dela** (amigas, blogueiras da mesma cidade). Também veja as lojas/marcas que ela
  marca e, nelas, quem mais aparece marcado.
- **hashtag**: `https://www.instagram.com/explore/tags/<tag>/` — olhe os posts recentes e
  os reels, abra os autores.
- **local**: pesquise o nome da cidade na busca → aba Locais (ou posts marcados naquela
  cidade). Perfis de mulheres da cidade que postam muito com localização marcada.
- **busca**: pesquise o termo na busca do Instagram (contas) e abra os resultados.
- **explorar / reels**: quando encontrar uma boa, olhe também quem ela marca e quem a marca.

**O que as 15 fechadas têm em comum** (ver `referencias/referencias_iniciais.json`):
- categoria "Blogueiro(a)" ou "Criador de conteúdo digital", bio "parcerias no direct";
- muitas são **mães** ("mamãe de…", "mãe da…", "mãe de primeira viagem");
- **poucos posts no feed é normal** (6, 7, 19, 31 posts e deram resultado). O que importa
  são stories ativos (anel colorido) e destaques;
- seguem bastante gente (seguindo alto não é problema);
- conteúdo de selfie, looks, praia, reels de POV com frase, humor do dia a dia, forró;
- Nordeste/Norte, cidade pequena (Anajatuba-MA, Ariquemes-RO), Fortaleza, João Pessoa;
- "Seguido(a) por" mostrando agência (fly.creators.br, hub.influ.br) ou outra parceira.

Sinais bons de cara: bio com "blogueira", "digital influencer", "publi", "parcerias",
"contato/WhatsApp", cidade/estado (MA, 📍São Luís, 📍Imperatriz…), "mãe de…", "mãe solo",
reels com legenda pedindo para assistir/compartilhar, recebidos de lojas locais.

## 3. Para cada candidata

1. Junte os @ que achou (pela lista, sem abrir os perfis ainda) e verifique em lote quais são novos:
   ```bash
   python propsec.py existe @a @b @c
   ```
   Pule os `JA_EXISTE`. Para cada `NOVO`, **rode `liberar` antes de abrir** (regra 1).
2. **Triagem rápida** (no topo do perfil). Descarte e registre como `ignorado` se:
   - menos de 1.000 seguidores;
   - mais de 20.000 **e** sem cara das referências (3 fechadas com 47k–139k deram resultado,
     então acima de 20k salve se for mãe/blogueira com público engajado e stories ativos,
     e escreva "caso especial" nas observações);
   - perfil privado, loja, página de memes/notícias, homem, empresa, perfil abandonado
     (último post há mais de 2 meses);
   - claramente comprado (ex.: 15 mil seguidores e posts com 20 curtidas e comentários de bots).

   Registrar o ignorado evita revisitar:
   ```bash
   echo '{"username":"x","seguidores":42000,"observacoes":"fora da faixa","origem":"hashtag","origem_detalhe":"publi"}' | python propsec.py salvar - --status ignorado
   ```
3. **Coleta completa** (só para quem passou na triagem). Gaste no máximo ~2 minutos por perfil:
   - **Topo:** nome, seguidores, seguindo, nº de posts, bio, link da bio, contato
     (WhatsApp/e-mail na bio ou botão de contato), cidade/UF (bio, localizações marcadas).
   - **Aba Reels:** anote as views dos 9–12 reels mais recentes (ignore fixados).
     Use a **mediana** (não a média; um viral distorce) → `media_views_reels`.
   - **3 a 5 posts recentes:** curtidas e nº de comentários (médias). Leia os comentários:
     são pessoas reais conversando, ela responde? → `comentarios_reais` de 0 a 1
     (1 = quase tudo gente real conversando; 0 = emojis genéricos/bots).
   - **Frequência:** pelas datas dos últimos posts → `posts_por_semana`.
   - **Stories:** tem anel de story ativo agora? Destaques atualizados recentemente?
     → `stories_ativos` (1/0). Pode abrir os stories só para olhar; **não reaja nem responda**.
   - **Publi:** já fez publi/permuta (#publi, "parceria", "recebidos", lojas marcadas)?
     → `faz_publi`, `marca_lojas`.
   - **Públicos** (etiquetas livres, sem forçar): `mãe solo`, `maternidade`,
     `mulher de preso`, `moda`, `beleza`, `fitness`, `humor`, `lifestyle`, `evangélica`,
     `periferia`, `interior`, `universitária` etc.
   - `tipo_conteudo`: ex. "reels de humor, rotina, provador de lojas".
   - `hashtags`: as que ela mais usa.
   - `observacoes`: 1–2 frases com o motivo de ser interessante ("bem conhecida em Codó,
     comentários de gente da cidade, faz publi de lojas locais").
4. **Salvar** (um JSON por perfil ou uma lista):
   ```bash
   python propsec.py salvar - <<'JSON'
   {"username": "maria.blog", "nome": "Maria", "cidade": "Codó", "uf": "MA",
    "seguidores": 6200, "seguindo": 900, "posts": 410,
    "media_views_reels": 4800, "media_curtidas": 380, "media_comentarios": 35,
    "comentarios_reais": 0.8, "posts_por_semana": 4, "stories_ativos": 1,
    "faz_publi": 1, "marca_lojas": 1, "contato": "wa.me/5599...",
    "link_bio": "...", "bio": "...", "publicos": ["mãe solo", "moda"],
    "tipo_conteudo": "rotina, provador de lojas", "hashtags": "#codoma #publi",
    "observacoes": "...", "origem": "similar", "origem_detalhe": "@perfil_referencia"}
   JSON
   ```
   `origem`/`origem_detalhe` devem ser **exatamente** o tipo e o valor da fonte
   (ex.: `hashtag` + `blogueiramaranhense`, `local` + `Codó`, `similar` + `nome_do_perfil`)
   — é assim que o sistema aprende quais fontes rendem. Campo que você não conseguiu ver:
   **omita** (não invente, não coloque 0).

## 4. Ritmo

O ritmo é controlado pelo porteiro (`liberar`): ele sorteia a espera entre perfis e faz
pausas longas periódicas. Não acelere entre as chamadas: gaste o tempo de cada perfil
olhando com calma (rolar, abrir posts e reels).

## 5. Encerrar

Para cada fonte explorada:
```bash
python propsec.py fonte <tipo> "<valor>" --vistos <quantos perfis olhou nela>
```
Depois:
```bash
python propsec.py sessao fim --visitados <total visitados> --salvos <total salvos (sem ignorados)>
python propsec.py resumo
```

Responda ao usuário com: quantos perfis visitou, quantos bons salvou, os 5 melhores
(@, cidade, seguidores, views médias dos reels, por que vale) e qual fonte rendeu mais.
Lembre que a fila está em http://localhost:8000/fila para aprovar/descartar.
