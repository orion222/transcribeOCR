import "@testing-library/jest-dom";

// jsdom does not implement matchMedia. Mantine's color-scheme handling and
// useMediaQuery both call it, so every component test needs it stubbed.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
