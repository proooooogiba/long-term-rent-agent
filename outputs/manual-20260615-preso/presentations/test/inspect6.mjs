import * as art from '@oai/artifact-tool';
const p = art.Presentation.create({slideSize:{width:1280,height:720}});
const s = p.slides.add();
for (const key of ['panel','text','image','shape','grid','row','column','card','rule']) {
  const fn = s.compose[key];
  console.log('FN', key, typeof fn === 'function' ? fn.toString().slice(0,500).replace(/\n/g,' ') : typeof fn);
}
