import * as art from '@oai/artifact-tool';
const p = art.Presentation.create({slideSize:{width:1280,height:720}});
const s = p.slides.add();
console.log(String(s.compose).slice(0,1200));
