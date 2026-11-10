// Registers a stub "@opencode/plugin" with bun, for the runners that load opencode plugin files.
// Import it before the plugin is loaded; the plugin is then imported dynamically, since a static
// import of it would be evaluated before this module's registration.

Bun.plugin({
  setup(b) {
    b.module("@opencode/plugin", () => ({ loader: "object", exports: { Plugin: { define: (x: unknown) => x } } }))
  },
})
