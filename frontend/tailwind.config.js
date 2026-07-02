/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm yellow-beige aesthetic (PLAN §6).
        cream: "#F5EFE6",
        surface: "#FFFBF3",
        border: "#E5DCC9",
        ink: "#1D1A16",
        muted: "#6B6355",
        amber: {
          DEFAULT: "#F5B942",
          dark: "#E0A62F",
        },
        good: "#3F8A4E",
        bad: "#C4483B",
      },
      borderRadius: {
        xl: "0.9rem",
        "2xl": "1.25rem",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
