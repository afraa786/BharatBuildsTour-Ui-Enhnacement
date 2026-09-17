const { WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN, OPENAI_API_KEY } = process.env;

async function askOpenAI(userText) {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${OPENAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      messages: [
        { role: "system", content: "You are StockAware, a helpful WhatsApp assistant for a wholesale business. Keep replies short." },
        { role: "user", content: userText },
      ],
    }),
  });
  const data = await res.json();
  return data.choices?.[0]?.message?.content || "Sorry, I couldn't process that.";
}

async function sendWhatsAppMessage(to, text) {
  const res = await fetch(`https://graph.facebook.com/v21.0/${WHATSAPP_PHONE_NUMBER_ID}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${WHATSAPP_ACCESS_TOKEN}`,
    },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to,
      text: { body: text },
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    console.error("whatsapp send failed", res.status, JSON.stringify(data));
  }
  return data;
}

module.exports = async (req, res) => {
  if (req.method === "GET") {
    const mode = req.query["hub.mode"];
    const token = req.query["hub.verify_token"];
    const challenge = req.query["hub.challenge"];
    if (mode === "subscribe" && token === WHATSAPP_VERIFY_TOKEN) {
      res.status(200).send(challenge);
    } else {
      res.status(403).send("Forbidden");
    }
    return;
  }

  if (req.method === "POST") {
    try {
      const entry = req.body?.entry?.[0];
      const change = entry?.changes?.[0]?.value;
      const message = change?.messages?.[0];
      if (message?.type === "text") {
        const from = message.from;
        const reply = await askOpenAI(message.text.body);
        await sendWhatsAppMessage(from, reply);
      }
    } catch (err) {
      console.error("webhook error", err);
    }
    res.status(200).send("EVENT_RECEIVED");
    return;
  }

  res.status(405).send("Method Not Allowed");
};
