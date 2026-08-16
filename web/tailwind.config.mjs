/** @type {import("tailwindcss").Config} */
export default {
  content: ["./src/**/*.{astro,html,js,ts}"],
  theme: {
    extend: {
      colors: {
        ink: "#171717",
        muted: "#6e6e73",
        line: "#d2d2d7",
        paper: "#f5f5f7",
        forge: "#0071e3",
        "forge-dark": "#005bb5",
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
