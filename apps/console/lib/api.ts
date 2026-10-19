import {
  KeysetListResponse,
  ObjectDetailResponse,
  NeighborsResponse,
  PropertyLineageResponse,
  DriftEvent,
  ReviewQueueItem,
} from "./types";

const API_BASE = "/api/foundry";

export async function fetchObjects(
  type: string,
  params?: {
    q?: string;
    filters?: string;
    cursor?: string;
    limit?: number;
  },
  headers?: Record<string, string>
): Promise<KeysetListResponse> {
  const query = new URLSearchParams();
  if (params?.q) query.set("q", params.q);
  if (params?.filters) query.set("filters", params.filters);
  if (params?.cursor) query.set("cursor", params.cursor);
  if (params?.limit) query.set("limit", String(params.limit));

  const url = `${API_BASE}/objects/${type}?${query.toString()}`;
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch ${type}: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchObjectDetail(
  type: string,
  id: string,
  headers?: Record<string, string>
): Promise<ObjectDetailResponse> {
  const url = `${API_BASE}/objects/${type}/${id}`;
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch ${type}/${id}: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchNeighbors(
  type: string,
  id: string,
  depth: number = 1,
  link?: string,
  headers?: Record<string, string>
): Promise<NeighborsResponse> {
  const query = new URLSearchParams();
  query.set("depth", String(depth));
  if (link) query.set("link", link);

  const url = `${API_BASE}/objects/${type}/${id}/neighbors?${query.toString()}`;
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch neighbors: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function executeTypedQuery(
  body: {
    type: string;
    filters?: Array<{ prop: string; op: string; value: any }>;
    traverse?: string[];
    limit?: number;
  },
  headers?: Record<string, string>
): Promise<KeysetListResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`DSL Query failed: ${res.status} ${err}`);
  }
  return res.json();
}

export async function fetchPropertyLineage(
  type: string,
  id: string,
  property: string,
  headers?: Record<string, string>
): Promise<PropertyLineageResponse> {
  const url = `${API_BASE}/lineage/${type}/${id}/${property}`;
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch lineage: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchDriftEvents(
  headers?: Record<string, string>
): Promise<DriftEvent[]> {
  const res = await fetch(`${API_BASE}/drift/events`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch drift events: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function approveDrift(
  eventId: string,
  headers?: Record<string, string>
): Promise<any> {
  const res = await fetch(`${API_BASE}/drift/${eventId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({ approved_by: "analyst" }),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to approve drift: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function rejectDrift(
  eventId: string,
  headers?: Record<string, string>
): Promise<any> {
  const res = await fetch(`${API_BASE}/drift/${eventId}/reject`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({ approved_by: "analyst" }),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to reject drift: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchReviewQueue(
  headers?: Record<string, string>
): Promise<{ count: number; items: ReviewQueueItem[] }> {
  const res = await fetch(`${API_BASE}/review-queue`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch review queue: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function submitReviewDecision(
  pairId: string,
  decision: "match" | "non_match",
  headers?: Record<string, string>
): Promise<any> {
  const res = await fetch(`${API_BASE}/review-queue/${pairId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({ decision }),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to submit review decision: ${res.status} ${errorText}`);
  }
  return res.json();
}
