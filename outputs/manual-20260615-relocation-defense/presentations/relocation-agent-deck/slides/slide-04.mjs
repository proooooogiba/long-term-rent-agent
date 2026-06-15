import { fixed, fr, grow, image, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, bulletLine, asset, assetImageSource } from "./common.mjs";

export async function addSlide(presentation, ctx) {
  const slide = presentation.slides.add();
  const contourImage = await assetImageSource(asset(ctx, "relocation_agent_architecture.drawio.png"));

  const contour = card(
    [
      image({ ...contourImage, fit: "contain", width: grow(1), height: fixed(392) }),
      text("Схема заземляет архитектуру; справа показано, что уже есть в прототипе и что нужно для боевого контура.", {
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

  const freshness = card(
    [
      chip("freshness", "blue"),
      text("Для данных есть явный operating contract.", { style: styles.cardTitle }),
      bulletLine("локальный каталог обновляется refresh job по trigger"),
      bulletLine("после 24 часов показываем staleness warning"),
      bulletLine("policy corpus пересматривается по weekly cadence"),
    ],
    { rows: [fixed(28), fixed(24), fixed(22), fixed(22), fixed(22)] },
  );

  const implemented = card(
    [
      chip("уже есть", "amber"),
      text("Что реально реализовано в прототипе.", { style: styles.cardTitle }),
      bulletLine("persistent memory в SQLite"),
      bulletLine("write-back в профиль кейса"),
      bulletLine("fallback при сбое MCP provider"),
    ],
    { rows: [fixed(28), fixed(48), fixed(22), fixed(22), fixed(22)] },
  );

  const observability = card(
    [
      chip("observability", "teal"),
      text("Ключевые сигналы уже определены.", { style: styles.cardTitle }),
      bulletLine("latency: agent_run, listing_search, MCP"),
      bulletLine("quality: nightly QA gate и quality gate status"),
      bulletLine("empty_shortlist_rate, escalation_rate, freshness age"),
    ],
    { rows: [fixed(28), fixed(24), fixed(22), fixed(22), fixed(22)] },
  );

  slide.compose(
    page(
      {
        header: header("Production operating model", "Слайд отвечает на вопрос: как агент живёт в боевом контуре, а не только в demo.", "Operating model"),
        body: row([fixed(760), fr(1)], [contour, column([fixed(156), fixed(168), fr(1)], [freshness, implemented, observability], 16)], 20),
      },
      "Ограничения и target-state взяты из production_operating_model.md.",
    ),
  );

  return slide;
}
