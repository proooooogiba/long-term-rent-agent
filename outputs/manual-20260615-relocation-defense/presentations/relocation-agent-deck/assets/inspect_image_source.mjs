import * as art from '@oai/artifact-tool';
for (const input of [
  {src:'/tmp/a.png'},
  {path:'/tmp/a.png'},
  {source:'/tmp/a.png'},
  {url:'/tmp/a.png'},
]) {
  try {
    console.log(JSON.stringify(art.image(input), null, 2));
  } catch (e) {
    console.log('ERR', JSON.stringify(input), e.message);
  }
}
