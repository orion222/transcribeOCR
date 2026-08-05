// frontend/src/testUtils.jsx
//
// Mantine components must render inside a MantineProvider. Component tests
// import { render } from here instead of from @testing-library/react so the
// provider is always present. Pure-logic tests (state.test.js, upload.test.js)
// don't need this.
//
// Note: deliberately no `export * from "@testing-library/react"` — a star
// export competes with the local `render` below and wins under Vite's interop,
// silently dropping the provider wrapper. Re-export explicitly instead.
import { MantineProvider } from "@mantine/core";
import * as rtl from "@testing-library/react";

function Providers({ children }) {
  return <MantineProvider>{children}</MantineProvider>;
}

export function render(ui, options) {
  return rtl.render(ui, { wrapper: Providers, ...options });
}

export const { screen, fireEvent, waitFor, within, act, cleanup, renderHook } = rtl;
