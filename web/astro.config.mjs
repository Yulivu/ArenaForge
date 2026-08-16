import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://yulivu.github.io",
  base: "/ArenaForge",
  output: "static",
  integrations: [tailwind()],
});
