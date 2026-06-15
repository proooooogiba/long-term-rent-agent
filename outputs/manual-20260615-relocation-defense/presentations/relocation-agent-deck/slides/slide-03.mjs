import { fixed, fr, grow, image, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, bulletLine, asset, assetImageSource } from "./common.mjs";

export async function addSlide(presentation, ctx) {
  const slide = presentation.slides.add();
  const workflowImageSource = await assetImageSource(asset(ctx, "relocation_agent_functional_flow.drawio.png"));

  const workflowImage = card(
    [
      image({ ...workflowImageSource, fit: "contain", width: grow(1), height: fixed(320) }),
      text("Функциональный flow: запрос -> поиск вариантов -> ранжирование -> проверка ограничений -> ответ.", {
        style: styles.cardBody,
        width: grow(1),
      }),
    ],
    {
      padding: { top: 12, right: 14, bottom: 14, left: 14 },
      rows: [fixed(320), fixed(38)],
      height: grow(1),
    },
  );

  const memoryCard = card(
    [
      chip("insta memory", "blue"),
      text("После run агент помнит состояние кейса.", { style: styles.cardTitle, width: grow(1) }),
      bulletLine("last_state, прошлый shortlist и case memory"),
    ],
    {
      rows: [fixed(28), fixed(34), fixed(20)],
      gap: 4,
      padding: { top: 10, right: 14, bottom: 10, left: 14 },
    },
  );

  const toolsCard = card(
    [
      chip("tools", "teal"),
      text("Tool layer детерминирован.", { style: styles.cardTitle, width: grow(1) }),
      row([fr(1), fr(1), fr(1)], [chip("RAG", "blue"), chip("БД", "teal"), chip("MCP", "amber")], 8),
      bulletLine("policy search, SQLite, scoring и MCP"),
    ],
    {
      rows: [fixed(28), fixed(30), fixed(30), fixed(24)],
      gap: 4,
      padding: { top: 10, right: 14, bottom: 10, left: 14 },
    },
  );

  const llmCard = card(
    [
      chip("зачем так", "amber"),
      text("LLM включаем только для недетерминированных шагов.", { style: styles.cardTitle, width: grow(1) }),
      bulletLine("router, intake, replanner, final composer"),
      bulletLine("поиск, ранжирование и проверки - в коде"),
    ],
    {
      rows: [fixed(28), fixed(42), fixed(20), fixed(20)],
      gap: 4,
      padding: { top: 10, right: 14, bottom: 10, left: 14 },
    },
  );

  slide.compose(
    page(
      {
        header: header("Как агент принимает решение", "Верхнеуровневый workflow связывает понимание запроса, память, тулы и локальную базу.", "Workflow"),
        body: row(
          [fixed(760), fr(1)],
          [
            workflowImage,
            column([fixed(100), fixed(126), fixed(132)], [memoryCard, toolsCard, llmCard], 12),
          ],
          20,
        ),
      },
      "Слева - functional flow из drawio, справа - память, tool layer и роль LLM.",
    ),
  );

  return slide;
}
