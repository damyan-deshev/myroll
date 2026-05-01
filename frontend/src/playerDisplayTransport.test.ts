import { describe, expect, it } from "vitest";
import {
  makeTransportMessage,
  parseTransportData,
  parseWindowMessage,
  PLAYER_DISPLAY_NAMESPACE
} from "./playerDisplayTransport";

describe("player display transport", () => {
  it("accepts namespaced notification messages", () => {
    const message = makeTransportMessage("display-state-changed", "display-1", {
      revision: 12,
      identify_revision: 3
    });

    expect(parseTransportData(message)).toMatchObject({
      namespace: PLAYER_DISPLAY_NAMESPACE,
      type: "display-state-changed",
      displayWindowId: "display-1",
      revision: 12,
      identify_revision: 3
    });
  });

  it("rejects wrong origin, wrong namespace, and content-bearing messages", () => {
    const message = makeTransportMessage("heartbeat", "display-1", {
      revision: 1,
      identify_revision: 0
    });

    expect(parseWindowMessage({ origin: "https://wrong.local", data: message } as MessageEvent, "http://localhost")).toBeNull();
    expect(parseTransportData({ ...message, namespace: "other" })).toBeNull();
    expect(parseTransportData({ ...message, title: "Private Scene Name" })).toBeNull();
    expect(parseTransportData({ ...message, payload: { title: "Nope" } })).toBeNull();
    expect(parseTransportData({ ...message, asset_url: "/api/player-display/assets/asset/blob" })).toBeNull();
    expect(parseTransportData({ ...message, mask_url: "/api/player-display/fog/fog-id/mask" })).toBeNull();
  });
});
