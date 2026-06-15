import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

async function writeBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function toManifestRelative(baseDir, targetPath) {
  const relativePath = path.relative(baseDir, targetPath) || ".";
  return relativePath.split(path.sep).join("/");
}

async function main() {
  const workspaceDir = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd();
  const slidesDir = path.join(workspaceDir, "slides");
  const previewDir = path.join(workspaceDir, "preview");
  const layoutDir = path.join(workspaceDir, "layout");
  const qaDir = path.join(workspaceDir, "qa");
  const outputDir = path.join(workspaceDir, "output");
  const outputPath = path.join(outputDir, "relocation-agent-defense.pptx");
  const manifestPath = path.join(qaDir, "manifest.json");
  const contactSheetPath = path.join(qaDir, "contact-sheet.png");
  const manifestBaseDir = path.dirname(manifestPath);
  const python = process.env.CODEX_PYTHON || "/Users/iopogiba/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
  const contactScript = process.env.CONTACT_SHEET_SCRIPT || "/Users/iopogiba/.codex/plugins/cache/openai-primary-runtime/presentations/26.614.11602/skills/presentations/scripts/make_contact_sheet.py";

  await Promise.all([
    fs.mkdir(previewDir, { recursive: true }),
    fs.mkdir(layoutDir, { recursive: true }),
    fs.mkdir(qaDir, { recursive: true }),
    fs.mkdir(outputDir, { recursive: true }),
  ]);

  const presentation = Presentation.create({
    slideSize: { width: 1280, height: 720 },
  });

  const ctx = { assetDir: path.join(workspaceDir, "assets") };
  const slideFiles = (await fs.readdir(slidesDir))
    .filter((name) => /^slide-\d+\.mjs$/.test(name))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

  const slideManifests = [];
  for (const [index, fileName] of slideFiles.entries()) {
    const modulePath = path.join(slidesDir, fileName);
    const mod = await import(pathToFileURL(modulePath).href);
    const exportName = "addSlide";
    await mod[exportName](presentation, ctx);
    slideManifests.push({
      index: index + 1,
      requestedSlideNumber: Number(fileName.match(/\d+/)?.[0] || index + 1),
      modulePath: toManifestRelative(manifestBaseDir, modulePath),
      exportName,
    });
  }

  const previewFilePaths = [];
  const previewPaths = [];
  const layoutResults = [];
  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    const pngPath = path.join(previewDir, `${stem}.png`);
    const layoutPath = path.join(layoutDir, `${stem}.layout.json`);

    await writeBlob(pngPath, await presentation.export({ slide, format: "png", scale: 1 }));
    const layoutBlob = await slide.export({ format: "layout" });
    await fs.writeFile(layoutPath, await layoutBlob.text(), "utf8");

    previewFilePaths.push(pngPath);
    previewPaths.push(toManifestRelative(manifestBaseDir, pngPath));
    layoutResults.push({ layoutPath: toManifestRelative(manifestBaseDir, layoutPath) });
  }

  const contactSheet = spawnSync(python, [contactScript, "--output", contactSheetPath, ...previewFilePaths], {
    encoding: "utf8",
  });
  if (contactSheet.status !== 0) {
    throw new Error(contactSheet.stderr || contactSheet.stdout || "Failed to render contact sheet");
  }

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(outputPath);
  const stat = await fs.stat(outputPath);

  const manifest = {
    output: toManifestRelative(manifestBaseDir, outputPath),
    outputBytes: stat.size,
    slideCount: presentation.slides.items.length,
    slideSize: { width: 1280, height: 720 },
    previewDir: toManifestRelative(manifestBaseDir, previewDir),
    previewPaths,
    layoutDir: toManifestRelative(manifestBaseDir, layoutDir),
    layoutResults,
    contactSheet: toManifestRelative(manifestBaseDir, contactSheetPath),
    slides: slideManifests,
  };
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
  console.log(JSON.stringify(manifest, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
