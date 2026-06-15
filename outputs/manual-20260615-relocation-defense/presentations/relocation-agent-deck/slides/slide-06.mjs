import { fixed, fr, grow, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, screenshotCard, asset, assetImageSource, bulletLine } from "./common.mjs";

export async function addSlide(presentation, ctx) {
  const slide = presentation.slides.add();
  const searchUi = await assetImageSource(asset(ctx, "search_ui.png"));
  const replanningUi = await assetImageSource(asset(ctx, "replanning_ui.png"));
  const escalationUi = await assetImageSource(asset(ctx, "escalation_ui.png"));

  const intro = row(
    [fixed(320), fr(1)],
    [
      card(
        [
          chip("demo mode", "amber"),
          text("Без живой LLM, но с тем же пайплайном", { style: styles.cardTitle }),
          bulletLine("demo_stub заменяет только недетерминированные шаги"),
          bulletLine("search, scoring и verifier работают как обычно"),
          bulletLine("поэтому скриншоты и повторяемость честные"),
        ],
        { rows: [fixed(28), fixed(48), fixed(22), fixed(22), fixed(22)] },
      ),
      card(
        [
          text("Что показать на защите", { style: styles.cardTitle }),
          row(
            [fr(1), fr(1), fr(1)],
            [
              text("1. Search: top-3 shortlist", { style: styles.body }),
              text("2. Replanning: изменение бюджета", { style: styles.body }),
              text("3. Escalation: document risk", { style: styles.body }),
            ],
            14,
          ),
        ],
        { rows: [fixed(26), fr(1)] },
      ),
    ],
    18,
  );

  const shots = row(
    [fr(1), fr(1), fr(1)],
    [
      screenshotCard(searchUi, "Search", "Happy path: кейс R-0002, top-3 и вкладка shortlist."),
      screenshotCard(replanningUi, "Replanning", "Changed constraints видно прямо в состоянии агента."),
      screenshotCard(escalationUi, "Escalation", "Verifier не даёт unsafe shortlist и предлагает human handoff."),
    ],
    14,
  );

  slide.compose(
    page(
      {
        header: header("Отдельный demo режим", "Этот слайд оставлен под демонстрацию: какие кейсы есть и почему demo работает без живой LLM.", "Demo"),
        body: column([fixed(210), fr(1)], [intro, shots], 18),
      },
      "Сценарии и скриншоты взяты из demo_scenarios.md и docs/demo_assets.",
    ),
  );

  return slide;
}
