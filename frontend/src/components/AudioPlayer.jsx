import "html-midi-player";

const SOUNDFONT =
  "https://storage.googleapis.com/magentadata/js/soundfonts/sgm_plus";

export default function AudioPlayer({ src }) {
  return <midi-player src={src} sound-font={SOUNDFONT} />;
}
