import { fixed, fr, grow, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, bulletLine, statCard } from "./common.mjs";

export async function addSlide(presentation) {
  const slide = presentation.slides.add();

  const rankingCard = card(
    [
      chip("shortlist score", "blue"),
      text("Как считается score shortlist", { style: styles.cardTitle }),
      text("Это внутренний ranking score для объявлений: он помогает упорядочить кандидатов до verifier и финального ответа.", {
        style: styles.cardBody,
        width: grow(1),
      }),
      row(
        [fr(1), fr(1), fr(1)],
        [
          statCard("25%", "budget fit", "blue"),
          statCard("20%", "commute fit", "teal"),
          statCard("20%", "household fit", "amber"),
        ],
        10,
      ),
      row(
        [fr(1), fr(1), fr(1)],
        [
          statCard("15%", "district fit", "blue"),
          statCard("10%", "pet fit", "teal"),
          statCard("10%", "upfront fit", "amber"),
        ],
        10,
      ),
    ],
    {
      rows: [fixed(28), fixed(24), fixed(46), fixed(92), fixed(92)],
      height: grow(1),
    },
  );

  const dataCard = card(
    [
      chip("на каких данных", "teal"),
      text("Что входит в расчёт shortlist score", { style: styles.cardTitle }),
      bulletLine("listing: rent, rooms, deposit, furnished, pet policy"),
      bulletLine("district: safety, transit, school, family-friendly"),
      bulletLine("requirements: budget, move-in date, pets, commute"),
    ],
    {
      rows: [fixed(28), fixed(24), fixed(22), fixed(22), fixed(22)],
      height: grow(1),
    },
  );

  const benchmarkCard = card(
    [
      chip("offline benchmark", "amber"),
      text("Как оцениваем модель офлайн", { style: styles.cardTitle }),
      bulletLine("тот же data/qa/qa.jsonl как suite"),
      bulletLine("для live LLM запускаем run_benchmark"),
      bulletLine("минимум 3 trial, лучше 5"),
      bulletLine("fresh SQLite для каждого trial"),
    ],
    { rows: [fixed(28), fixed(24), fixed(20), fixed(20), fixed(20), fixed(20)] },
  );

  const metricsCard = card(
    [
      chip("что сравниваем", "blue"),
      text("Метрики для сравнения вариантов", { style: styles.cardTitle }),
      bulletLine("domain metrics и quality gate"),
      bulletLine("mean_case_score и case pass rate"),
      bulletLine("case_pass_all_k и outcome_consistency"),
      bulletLine("mean latency и p95 latency"),
    ],
    { rows: [fixed(28), fixed(24), fixed(20), fixed(20), fixed(20), fixed(20)] },
  );

  const feedbackCard = card(
    [
      chip("human feedback", "red"),
      text("Как оцениваем live-режим", { style: styles.cardTitle }),
      bulletLine("task_completion, constraint_fit, relevance"),
      bulletLine("clarity, safety_trust, would_use_again"),
      bulletLine("critical_issue_yes_no как стоп-сигнал"),
      bulletLine("шаблон feedback лежит в data/qa"),
    ],
    { rows: [fixed(28), fixed(24), fixed(20), fixed(20), fixed(20), fixed(20)] },
  );

  slide.compose(
    page(
      {
        header: header("Как мы считаем score и как его проверяем", "Слева - внутренний score shortlist, справа - оценка качества модели через benchmark и human feedback.", "Quality"),
        body: row(
          [fixed(760), fr(1)],
          [
            column([fixed(322), fr(1)], [rankingCard, dataCard], 16),
            column([fixed(170), fixed(170), fixed(170)], [benchmarkCard, metricsCard, feedbackCard], 16),
          ],
          20,
        ),
      },
      "Score shortlist берётся из src/tools/calculations.py; evaluation framework - из docs/evaluation_framework.md.",
    ),
  );

  return slide;
}
