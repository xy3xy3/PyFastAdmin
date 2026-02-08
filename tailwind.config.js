/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/apps/**/templates/**/*.html", "./app/static/js/**/*.js"],
  theme: {
    extend: {
      fontFamily: {
        display: ["\"ZCOOL XiaoWei\"", "\"Noto Serif SC\"", "\"STSong\"", "serif"],
        body: ["\"LXGW WenKai\"", "\"Noto Sans SC\"", "\"PingFang SC\"", "\"Microsoft YaHei\"", "sans-serif"],
      },
      boxShadow: {
        ink: "0 20px 40px rgba(17, 20, 24, 0.18)",
        glow: "0 0 0 1px rgba(192, 64, 43, 0.25), 0 8px 26px rgba(192, 64, 43, 0.18)",
      },
      borderRadius: {
        blob: "2.25rem",
      },
    },
  },
  plugins: [],
};
