import { fixed, fr, grow, image, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, statCard, asset, assetImageSource } from "./common.mjs";

function featureCard(tag, title, body, tone) {
  return card(
    [
      chip(tag, tone),
      text(title, { style: styles.body, width: grow(1) }),
      text(body, { style: styles.bodySmall, width: grow(1) }),
    ],
    {
      rows: [fixed(28), fixed(28), fr(1)],
      padding: { top: 14, right: 16, bottom: 14, left: 16 },
      height: grow(1),
    },
  );
}

export async function addSlide(presentation, ctx) {
  const slide = presentation.slides.add();
  const architectureImage = await assetImageSource(asset(ctx, "relocation_agent_architecture.drawio.png"));

  const left = column(
    [fixed(28), fixed(90), fixed(58), fixed(248), fr(1)],
    [
      chip("Что показываем", "blue"),
      text("Как показать именно агента, а не просто хороший чат?", {
        style: styles.hero,
        width: grow(1),
      }),
      text("Смотрим не только на финальный ответ, а на весь управляемый путь: от понимания кейса до безопасного human handoff.", {
        style: styles.body,
        width: grow(1),
      }),
      row(
        [fr(1), fr(1)],
        [
          featureCard("подбор", "Подбор под кейс", "Город, бюджет, семья, питомцы и commute.", "blue"),
          featureCard("память", "Память между запусками", "Новый run помнит прошлый shortlist.", "teal"),
          featureCard("безопасность", "Безопасная остановка", "Риск идёт в clarification или handoff.", "amber"),
          featureCard("интеграции", "Live-источники", "MCP даёт свежие карточки, fallback остаётся локальным.", "red"),
        ],
        12,
      ),
      statCard("1 кейс", "1 run = shortlist + объяснение + guardrails", "teal"),
    ],
  );

  const right = column(
    [fixed(332), fr(1)],
    [
      card(
        [
          image({ ...architectureImage, fit: "contain", width: grow(1), height: fixed(248) }),
          text("Компонентная схема: UI -> orchestration graph -> memory -> tool layer -> data и MCP.", {
            style: styles.cardBody,
            width: grow(1),
          }),
        ],
        {
          rows: [fixed(248), fr(1)],
          padding: { top: 14, right: 16, bottom: 14, left: 16 },
        },
      ),
      row(
        [fr(1), fr(1)],
        [
          statCard("9", "узлов в trace", "blue"),
          statCard("3", "demo-сценария для защиты", "amber"),
        ],
        12,
      ),
    ],
    14,
  );

  slide.compose(
    page(
      {
        header: header("Агент подбора аренды и релокации", "От подбора по кейсу до безопасного решения с памятью, проверками и fallback-логикой.", "Финальная работа"),
        body: row([fr(1.18), fixed(420)], [left, right], 22),
      },
      "Дальше: продуктовая ценность -> workflow -> operating model -> MCP -> demo -> score -> trace -> проблемы.",
    ),
  );

  return slide;
}
