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

// jsdom does not implement the layout/measurement APIs React Flow relies on
// to decide it has something to draw. Without these, React Flow renders
// nothing under test: no size on the pane means "not ready" (no pane at
// all), a missing DOMMatrixReadOnly means reading the zoom level throws, and
// a missing SVGElement.getBBox means edge-label rendering throws. Anyone
// deleting one of these should expect that specific failure to come back.
if (!global.ResizeObserver) {
  global.ResizeObserver = class ResizeObserver {
    constructor(callback) {
      this.callback = callback;
    }

    observe(target) {
      // React Flow's container observer must fire at least once or the
      // pane never gets a size and nothing renders.
      this.callback([{ target }]);
    }

    unobserve() {}

    disconnect() {}
  };
}

if (!global.DOMMatrixReadOnly) {
  global.DOMMatrixReadOnly = class DOMMatrixReadOnly {
    constructor(transform) {
      const match = /scale\(([^)]+)\)/.exec(transform ?? "");
      const parsed = match ? parseFloat(match[1]) : NaN;
      this.m22 = Number.isNaN(parsed) ? 1 : parsed;
    }
  };
}

Object.defineProperties(HTMLElement.prototype, {
  offsetWidth: {
    configurable: true,
    get() {
      const width = parseFloat(this.style.width);
      return Number.isNaN(width) ? 1000 : width;
    },
  },
  offsetHeight: {
    configurable: true,
    get() {
      const height = parseFloat(this.style.height);
      return Number.isNaN(height) ? 400 : height;
    },
  },
});

HTMLElement.prototype.getBoundingClientRect = function getBoundingClientRect() {
  return {
    width: 1000,
    height: 400,
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 1000,
    bottom: 400,
    toJSON() {
      return this;
    },
  };
};

if (!SVGElement.prototype.getBBox) {
  SVGElement.prototype.getBBox = () => ({ x: 0, y: 0, width: 0, height: 0 });
}
