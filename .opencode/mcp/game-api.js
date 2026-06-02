#!/usr/bin/env node

const http = require("http");

const BASE = "http://localhost:8000";
const SID = "mcp-agent";

async function api(path, data = {}) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({ sid: SID, ...data }).toString();
    const req = http.request(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }, (res) => {
      let raw = "";
      res.on("data", (c) => raw += c);
      res.on("end", () => {
        try { resolve(JSON.parse(raw)); } catch { resolve(raw); }
      });
    });
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

const TOOLS = [
  {
    name: "create_fighter",
    description: "Create a new player fighter",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string" },
        age: { type: "number" },
        weight_class: { type: "number", description: "0=Strawweight..8=Heavyweight" },
        background: { type: "string", enum: ["mma", "boxing", "bjj", "wrestling", "muay_thai", "kickboxing", "karate", "taekwondo", "judo", "sambo"] },
        nationality: { type: "string" },
      },
    },
  },
  {
    name: "advance_day",
    description: "Advance game by one day (triggers training, fight week events, world sim)",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "get_state",
    description: "Get full game state for current session",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "book_fight",
    description: "Accept a fight offer",
    inputSchema: {
      type: "object",
      properties: {
        opponent: { type: "string", description: "Opponent name from fight offers" },
      },
      required: ["opponent"],
    },
  },
  {
    name: "get_fight_offers",
    description: "Get available fight offers",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "start_fight",
    description: "Start a booked fight with a strategy",
    inputSchema: {
      type: "object",
      properties: {
        strategy: {
          type: "string",
          enum: ["aggressive_striking", "counter_striker", "pressure_fighter", "volume_striker",
                 "accurate_boxer", "muay_thai_plod", "head_hunter", "body_attacker",
                 "wrestle_heavy", "grappler", "dirty_boxer", "clinch_fighter",
                 "bjj_specialist", "submission_hunter", "ground_and_pound",
                 "balanced", "defensive_grappler", "counter_wrestler"],
          description: "Fight strategy ID",
        },
      },
    },
  },
  {
    name: "fight_events",
    description: "Poll for new fight events from active fight stream",
    inputSchema: {
      type: "object",
      properties: {
        from: { type: "number", description: "Event index to start from (default: 0)" },
      },
    },
  },
  {
    name: "fight_action",
    description: "Submit a mid-fight strategy change",
    inputSchema: {
      type: "object",
      properties: {
        strategy: { type: "string", description: "New strategy ID" },
      },
      required: ["strategy"],
    },
  },
  {
    name: "complete_fight",
    description: "Finalize completed fight (process pay, rankings, etc.)",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "press_conference",
    description: "Choose press conference action during fight week",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["respectful", "trash_talk", "staredown"] },
      },
      required: ["action"],
    },
  },
  {
    name: "open_workout",
    description: "Choose open workout intensity during fight week",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["technical", "power", "showboat"] },
      },
      required: ["action"],
    },
  },
  {
    name: "cut_weight",
    description: "Choose weight cut intensity during fight week",
    inputSchema: {
      type: "object",
      properties: {
        intensity: { type: "string", enum: ["safe", "standard", "aggressive"] },
      },
      required: ["intensity"],
    },
  },
  {
    name: "faceoff",
    description: "Choose faceoff demeanor during fight week",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["intense", "calm", "dismissive"] },
      },
      required: ["action"],
    },
  },
  {
    name: "rest_day",
    description: "Choose rest day recovery activity during fight week",
    inputSchema: {
      type: "object",
      properties: {
        activity: { type: "string", enum: ["ice_bath", "massage", "meditation", "light_spar"] },
      },
      required: ["activity"],
    },
  },
  {
    name: "scout_opponent",
    description: "Scout current opponent to reveal stats",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "sign_contract",
    description: "Sign with a promotion",
    inputSchema: {
      type: "object",
      properties: {
        promotion: { type: "string", description: "Promotion name" },
      },
      required: ["promotion"],
    },
  },
];

async function handleToolCall(name, args) {
  const pathMap = {
    create_fighter: "/api/create_fighter",
    advance_day: "/api/advance_day",
    get_state: "/api/state",
    book_fight: "/api/fight_offer",
    get_fight_offers: "/api/fight_booking_state",
    start_fight: "/api/start_fight",
    fight_events: "/api/fight_events",
    fight_action: "/api/fight_action",
    complete_fight: "/api/complete_fight",
    press_conference: "/api/press_conference",
    open_workout: "/api/open_workout",
    cut_weight: "/api/cut_weight",
    faceoff: "/api/faceoff",
    rest_day: "/api/rest_day",
    scout_opponent: "/api/scout_opponent",
    sign_contract: "/api/sign_contract",
  };

  const path = pathMap[name];
  if (!path) throw new Error(`Unknown tool: ${name}`);

  if (name === "get_state") {
    const resp = await api("/api/state", { sid: SID });
    return { content: [{ type: "text", text: JSON.stringify(resp, null, 2) }] };
  }

  const resp = await api(path, args);
  return { content: [{ type: "text", text: JSON.stringify(resp, null, 2) }] };
}

const server = http.createServer(async (req, res) => {
  res.setHeader("Content-Type", "application/json");

  if (req.method === "GET" && req.url === "/health") {
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  if (req.method !== "POST") {
    res.statusCode = 405;
    res.end(JSON.stringify({ error: "Method not allowed" }));
    return;
  }

  let body = "";
  req.on("data", (c) => body += c);
  req.on("end", async () => {
    try {
      const msg = JSON.parse(body);

      if (msg.method === "tools/list") {
        res.end(JSON.stringify({ tools: TOOLS }));
      } else if (msg.method === "tools/call") {
        const result = await handleToolCall(msg.params.name, msg.params.arguments || {});
        res.end(JSON.stringify(result));
      } else {
        res.end(JSON.stringify({ error: `Unknown method: ${msg.method}` }));
      }
    } catch (e) {
      res.statusCode = 500;
      res.end(JSON.stringify({ error: e.message }));
    }
  });
});

const PORT = 3100;
server.listen(PORT, () => {
  console.error(`Game API MCP server running on port ${PORT}`);
});
