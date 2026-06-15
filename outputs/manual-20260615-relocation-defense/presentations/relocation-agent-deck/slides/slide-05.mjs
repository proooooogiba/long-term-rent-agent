import { fixed, fr, grow, image, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, bulletLine, asset, assetImageSource, statCard } from "./common.mjs";

export async function addSlide(presentation, ctx) {
  const slide = presentation.slides.add();
  const mcpImage = await assetImageSource(asset(ctx, "mcp_cian_flow.png"));

  const flow = card(
    [
      image({ ...mcpImage, fit: "contain", width: grow(1), height: fixed(392) }),
      text("Cian не живёт отдельно: его выдача нормализуется в ту же модель Listing и попадает в тот же shortlist.", {
        style: styles.cardBody,
        width: grow(1),
      }),
    ],
    {
      padding: { top: 10, right: 12, bottom: 12, left: 12 },
      rows: [fixed(392), fr(1)],
      height: grow(1),
    },
  );

  const verified = card(
    [
      chip("проверенный пример", "teal"),
      text("Live-capture от 2026-06-14", { style: styles.cardTitle }),
      bulletLine("провайдер: Apify MCP"),
      bulletLine("инструмент: cian-ru-scraper"),
      bulletLine("запрос: Moscow, 1 room, rent"),
    ],
    { rows: [fixed(28), fixed(24), fixed(22), fixed(22), fixed(22)] },
  );

  const prices = row(
    [fr(1), fr(1), fr(1)],
    [
      statCard("25k", "₽ • #998771", "blue"),
      statCard("38k", "₽ • #995460", "teal"),
      statCard("45k", "₽ • #992338", "amber"),
    ],
    10,
  );

  const contract = card(
    [
      chip("contract", "blue"),
      text("Почему этот слой важен", { style: styles.cardTitle }),
      bulletLine("новые providers чаще подключаются через config"),
      bulletLine("aliases, mapping и defaults живут вне графа"),
      bulletLine("timeout или provider fail -> fallback на локальные объявления"),
    ],
    { rows: [fixed(28), fixed(24), fixed(22), fixed(22), fixed(22)] },
  );

  slide.compose(
    page(
      {
        header: header("MCP Cian, с которым работает агент", "Внешний provider нужен для свежих карточек и цен, но не ломает систему при недоступности.", "External integration"),
        body: row(
          [fixed(760), fr(1)],
          [
            flow,
            column([fixed(156), fixed(96), fr(1)], [verified, prices, contract], 16),
          ],
          20,
        ),
      },
      "Факты на этом слайде взяты из external_mcp_provider_example.md и config/mcp_connectors.example.json.",
    ),
  );

  return slide;
}
