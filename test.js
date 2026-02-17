const { app, server } = require("./server");
const http = require("http");

const port = server.address().port;

const req = http.get(`http://localhost:${port}/health`, (res) => {
  let data = "";
  res.on("data", (chunk) => (data += chunk));
  res.on("end", () => {
    const body = JSON.parse(data);
    const passed =
      res.statusCode === 200 &&
      body.status === "ok" &&
      typeof body.timestamp === "string";
    console.log(passed ? "PASS" : "FAIL", body);
    server.close();
    process.exit(passed ? 0 : 1);
  });
});
req.on("error", (err) => {
  console.error("FAIL", err.message);
  server.close();
  process.exit(1);
});
