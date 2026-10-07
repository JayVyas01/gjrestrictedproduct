import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { contract, serveContract } from "@/test/handlers";
import { server } from "@/test/server";
import {
  ApiError,
  apiGet,
  apiPost,
  apiPut,
  ensureCsrf,
  lastActiveRequestAt,
  setPasswordChangeRequiredHandler,
  setSessionExpiredHandler,
} from "./client";

// Records the CSRF header of each request to `path`.
function recordCsrf(method: "get" | "post" | "put", path: string) {
  const seen: (string | null)[] = [];
  server.use(
    http[method](path, ({ request }) => {
      seen.push(request.headers.get("X-CSRFToken"));
      return HttpResponse.json({});
    }),
  );
  return seen;
}

function countCsrfFetches() {
  const calls = { count: 0 };
  server.use(
    http.get("/api/auth/csrf", () => {
      calls.count += 1;
      document.cookie = "csrftoken=mock-csrf-token; path=/";
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return calls;
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(
    () => undefined,
    (e: unknown) => e,
  );
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

describe("CSRF", () => {
  it("sends the token on POST and PUT, not on GET", async () => {
    const gets = recordCsrf("get", "/api/x");
    const posts = recordCsrf("post", "/api/x");
    const puts = recordCsrf("put", "/api/x");
    await apiGet("/api/x");
    await apiPost("/api/x", { a: 1 });
    await apiPut("/api/x", { a: 1 });
    expect(gets).toEqual([null]);
    expect(posts).toEqual(["mock-csrf-token"]);
    expect(puts).toEqual(["mock-csrf-token"]);
  });

  it("fetches the CSRF cookie once", async () => {
    recordCsrf("post", "/api/x");
    const calls = countCsrfFetches();
    await Promise.all([apiPost("/api/x"), apiPost("/api/x"), ensureCsrf()]);
    await apiPost("/api/x");
    expect(calls.count).toBe(1);
  });

  it("tries again after a failed CSRF fetch", async () => {
    server.use(
      http.get("/api/auth/csrf", () => HttpResponse.json({}, { status: 500 }), { once: true }),
    );
    await expect(ensureCsrf()).rejects.toBeInstanceOf(ApiError);
    await expect(ensureCsrf()).resolves.toBeUndefined();
  });

  it("reads the cookie fresh on each request (the server rotates it at sign-in)", async () => {
    const posts = recordCsrf("post", "/api/x");
    await apiPost("/api/x");
    document.cookie = "csrftoken=rotated; path=/";
    await apiPost("/api/x");
    expect(posts).toEqual(["mock-csrf-token", "rotated"]);
  });
});

describe("responses", () => {
  it("returns the parsed body", async () => {
    await expect(apiGet("/api/home")).resolves.toEqual(contract("home_licensee"));
  });

  it("returns undefined for 204 No Content", async () => {
    await expect(apiPost("/api/auth/logout")).resolves.toBeUndefined();
  });
});

describe("error mapping", () => {
  const TX = { method: "get", path: "/api/transactions/:reference" } as const;
  const NEW = { method: "post", path: "/api/transactions" } as const;

  it("400 carries field errors", async () => {
    server.use(serveContract("error_400_field_errors", NEW));
    const error = await failure(apiPost("/api/transactions", {}));
    expect(error.status).toBe(400);
    expect(error.fieldErrors).toEqual({
      vehicle_number: ["Enter the vehicle number like GJ01AB1234."],
    });
  });

  it("400 with only a detail has no field errors", async () => {
    server.use(
      serveContract("error_400_unknown_filter", { method: "get", path: "/api/transactions" }),
    );
    const error = await failure(apiGet("/api/transactions?side=both"));
    expect([error.status, error.detail, error.fieldErrors]).toEqual([
      400,
      "Unknown filter value.",
      undefined,
    ]);
  });

  it.each([
    ["error_401_wrong_code", 401],
    ["error_404_not_found", 404],
    ["error_409_conflict", 409],
  ])("%s keeps the status and the server's detail", async (name, status) => {
    server.use(serveContract(name, TX));
    const error = await failure(apiGet("/api/transactions/TX1"));
    expect(error.status).toBe(status);
    expect(error.detail).toBe(contract<{ detail: string }>(name).detail);
  });

  it("422 carries the reasons", async () => {
    server.use(serveContract("error_422_transaction_refused", NEW));
    const error = await failure(apiPost("/api/transactions", {}));
    expect(error.status).toBe(422);
    expect(error.detail).toBe("This transaction can't go ahead.");
    expect(error.reasons).toEqual(
      contract<{ reasons: string[] }>("error_422_transaction_refused").reasons,
    );
  });

  it("429 and 5xx without a JSON body still become ApiErrors", async () => {
    server.use(
      http.get("/api/a", () =>
        HttpResponse.json({ detail: "Request was throttled." }, { status: 429 }),
      ),
      http.get("/api/b", () => new HttpResponse("<h1>Server Error</h1>", { status: 500 })),
    );
    expect((await failure(apiGet("/api/a"))).status).toBe(429);
    const error = await failure(apiGet("/api/b"));
    expect([error.status, error.detail]).toEqual([500, ""]);
  });
});

describe("session expiry", () => {
  const FORBIDDEN = { method: "get", path: "/api/transactions/:reference" } as const;

  it("a 403 followed by a failed me calls the expiry handler", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    server.use(
      serveContract("error_403_not_allowed", FORBIDDEN),
      serveContract("error_403_not_signed_in", { method: "get", path: "/api/auth/me" }),
    );
    const error = await failure(apiGet("/api/transactions/TX1"));
    expect(error.status).toBe(403);
    expect(expired).toHaveBeenCalledOnce();
  });

  it("a 403 followed by a working me does not", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    server.use(serveContract("error_403_not_allowed", FORBIDDEN));
    const error = await failure(apiGet("/api/transactions/TX1"));
    expect(error.detail).toBe("This transaction is not waiting for your decision.");
    expect(expired).not.toHaveBeenCalled();
  });

  it("a 403 from me itself does not check me again", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    const calls = { count: 0 };
    server.use(
      http.get("/api/auth/me", () => {
        calls.count += 1;
        return HttpResponse.json(contract("error_403_not_signed_in"), { status: 403 });
      }),
    );
    await failure(apiGet("/api/auth/me"));
    expect(calls.count).toBe(1);
    expect(expired).not.toHaveBeenCalled();
  });
});

describe("password change required", () => {
  it("a 403 with code password_change_required calls its handler, not the expiry one", async () => {
    const expired = vi.fn();
    const changeFirst = vi.fn();
    setSessionExpiredHandler(expired);
    setPasswordChangeRequiredHandler(changeFirst);
    let meCalls = 0;
    server.use(
      serveContract("error_403_password_change_required", {
        method: "get",
        path: "/api/home",
      }),
      http.get("/api/auth/me", () => {
        meCalls += 1;
        return HttpResponse.json(contract("error_403_not_signed_in"), {
          status: 403,
        });
      }),
    );
    const error = await failure(apiGet("/api/home"));
    expect([error.status, error.code]).toEqual([403, "password_change_required"]);
    expect(error.fieldErrors).toBeUndefined();
    expect(changeFirst).toHaveBeenCalledOnce();
    expect(expired).not.toHaveBeenCalled();
    expect(meCalls).toBe(0);
  });
});

describe("sign-in requests", () => {
  it.each(["/api/auth/login", "/api/auth/login/verify"])(
    "a 403 from %s is not taken for an ended session",
    async (path) => {
      const expired = vi.fn();
      setSessionExpiredHandler(expired);
      let meCalls = 0;
      server.use(
        http.post(path, () => HttpResponse.json({ detail: "Locked." }, { status: 403 })),
        http.get("/api/auth/me", () => {
          meCalls += 1;
          return HttpResponse.json(contract("error_403_not_signed_in"), { status: 403 });
        }),
      );
      expect((await failure(apiPost(path, {}))).status).toBe(403);
      expect(meCalls).toBe(0);
      expect(expired).not.toHaveBeenCalled();
    },
  );
});

describe("background refreshes", () => {
  function recordBackground(path: string) {
    const seen: (string | null)[] = [];
    server.use(
      http.get(path, ({ request }) => {
        seen.push(request.headers.get("X-Background-Refresh"));
        return HttpResponse.json({});
      }),
    );
    return seen;
  }

  it("send X-Background-Refresh: 1 only when asked to", async () => {
    const seen = recordBackground("/api/x");
    await apiGet("/api/x", { background: true });
    await apiGet("/api/x");
    expect(seen).toEqual(["1", null]);
  });

  it("only requests that are not background refreshes count as activity", async () => {
    recordBackground("/api/x");
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      vi.setSystemTime(1_000_000);
      await apiGet("/api/x");
      expect(lastActiveRequestAt()).toBe(1_000_000);
      vi.setSystemTime(2_000_000);
      await apiGet("/api/x", { background: true });
      expect(lastActiveRequestAt()).toBe(1_000_000);
    } finally {
      vi.useRealTimers();
    }
  });
});
