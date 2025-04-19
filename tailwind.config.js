/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./martina_bescos_app/templates/**/*.html",
    "./evaluations/templates/**/*.html",
    "./api_keys/templates/**/*.html",
    "./martina_bescos_app/users/templates/**/*.html",
    "./martina_bescos_app/static/js/**/*.js",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark"],
  },
}
