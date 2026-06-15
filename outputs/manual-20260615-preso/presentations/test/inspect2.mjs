import * as art from '@oai/artifact-tool';
for (const key of ['composeSlide','slide','Presentation','PresentationFile','addTextToSlide','addImageToSlide']) {
  if (typeof art[key] === 'function') {
    console.log('FN', key, art[key].toString().slice(0,500).replace(/\n/g,' '));
  } else if (art[key] !== undefined) {
    console.log('VAL', key, typeof art[key], Object.keys(art[key]||{}).slice(0,20));
  }
}
