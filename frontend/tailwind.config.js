/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark navy sidebar / surfaces from the Blackline reference.
        ink: {
          900: "#0b1220",
          800: "#111a2e",
          700: "#1b2740",
        },
        accent: {
          DEFAULT: "#2563eb",
          soft: "#3b82f6",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
