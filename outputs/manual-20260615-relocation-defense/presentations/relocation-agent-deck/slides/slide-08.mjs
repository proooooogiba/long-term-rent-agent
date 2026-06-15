import { fixed, fr, grow, image, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, asset, assetImageSource, statCard, bulletLine } from "./common.mjs";

export async function addSlide(presentation, ctx) {
  const slide = presentation.slides.add();
  const traceImage = await assetImageSource(asset(ctx, "trace_timeline.png"));

  const trace = card(
    [
      image({ ...traceImage, fit: "contain", width: grow(1), height: fixed(408) }),
      text("Замерено через AgentTraceStep на live OpenRouter run от 2026-06-15.", {
        style: styles.cardBody,
        width: grow(1),
      }),
    ],
    {
      padding: { top: 10, right: 12, bottom: 12, left: 12 },
      rows: [fixed(408), fr(1)],
      height: grow(1),
    },
  );

  const totals = row(
    [fr(1), fr(1), fr(1)],
    [
      statCard("10.2 s", "общий run", "blue"),
      statCard("5.4 s", "intake", "teal"),
      statCard("3.2 s", "final composer", "amber"),
    ],
    12,
  );

  const why = card(
    [
      chip("зачем это нужно", "blue"),
      text("Trace показывает не только latency, но и реальный маршрут запроса.", { style: styles.cardTitle }),
      bulletLine("видно шаги, которые агент реально прошёл"),
      bulletLine("видно момент ухода в clarification"),
    ],
    { rows: [fixed(28), fixed(64), fixed(24), fixed(24)] },
  );

  const focus = card(
    [
      chip("наблюдение", "teal"),
      text("В этом live кейсе почти вся стоимость сидит в LLM-узлах.", { style: styles.cardTitle }),
      bulletLine("router + intake + final composer = 10.19 s"),
      bulletLine("детерминированный контур занял около 6 ms"),
    ],
    { rows: [fixed(28), fixed(64), fixed(24), fixed(24)] },
  );

  slide.compose(
    page(
      {
        header: header("Сколько времени занимает каждый этап", "Показываем live trace одного run, а не абстрактное 'агент что-то думает'.", "Trace"),
        body: row([fixed(760), fr(1)], [trace, column([fixed(96), fixed(180), fr(1)], [totals, why, focus], 16)], 20),
      },
      "Тайминги сняты из live OpenRouter run; breakdown взят из AgentTraceStep.duration_ms. На этом кейсе budget не извлёкся и сценарий ушёл в clarification.",
    ),
  );

  return slide;
}
