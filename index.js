const express = require('express');

const app = express();
const PORT = process.env.PORT || 3000;

app.get('/goodbye', (req, res) => {
  res.send('Goodbye, World!');
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
