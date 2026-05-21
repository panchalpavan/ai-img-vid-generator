"use client";

/**
 * Reference Library hooks (Sprint 4A.3).
 *
 * Three hooks here because the upload flow has three pieces:
 *
 *   - useReferences()        — query: list current user's refs (gallery + picker)
 *   - useUploadReference()   — mutation: presign → PUT → complete, returns the row
 *   - useDeleteReference()   — mutation: delete from R2 + DB
 *
 * The upload flow is deliberately a *single* mutation from the caller's POV
 * (one `mutate(file)` call) even though there are three network round-trips
 * under the hood: presign → PUT to R2 → complete. Splitting them at the hook
 * layer would force every consumer to wire three mutations together.
 *
 * The middle PUT bypasses our `apiPost` helper because:
 *   - The signed URL is on R2's S3 endpoint, not our API.
 *   - It needs NO `Authorization: Bearer ...` header (auth is in the signature).
 *   - The body is a raw `Blob`, not JSON.
 *   - The Content-Type header MUST match what we signed for, exactly.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "./client";
import type {
  CompleteRequest,
  PresignRequest,
  PresignResponse,
  ReferenceResponse,
} from "./types";

const REFERENCES_QUERY_KEY = ["references"] as const;

/** List the current user's references, newest first. */
export function useReferences() {
  return useQuery<ReferenceResponse[], Error>({
    queryKey: REFERENCES_QUERY_KEY,
    queryFn: () => apiGet<ReferenceResponse[]>("/references"),
  });
}

/** Upload a single file via the three-step presigned-URL flow.
 *
 * Returns a TanStack mutation. Call `.mutate(file)` (or `.mutateAsync(file)`)
 * with a browser `File`; the resolved value is the new `ReferenceResponse`.
 *
 * On success: invalidates the references list so a gallery reflects the
 * new ref immediately.
 */
export function useUploadReference() {
  const queryClient = useQueryClient();
  return useMutation<ReferenceResponse, Error, File>({
    mutationFn: uploadReferenceViaPresignedUrl,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: REFERENCES_QUERY_KEY });
    },
  });
}

/** Delete a reference (R2 object + DB row). */
export function useDeleteReference() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (referenceId) => {
      // No body, so apiPost doesn't fit. Inline fetch with the same JWT
      // mechanic the rest of the client uses. We import inside to keep the
      // hook surface clean; if delete becomes common we'll add apiDelete().
      const jwt = await fetch("/api/auth/token", { credentials: "include" })
        .then((r) => r.json() as Promise<{ token: string }>)
        .then((j) => j.token);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiUrl}/references/${referenceId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (!res.ok) {
        throw new Error(`Delete failed: ${res.status} ${res.statusText}`);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: REFERENCES_QUERY_KEY });
    },
  });
}

// ---------------------------------------------------------------------------
// The orchestrator — three round trips behind one function.
// ---------------------------------------------------------------------------

async function uploadReferenceViaPresignedUrl(
  file: File,
): Promise<ReferenceResponse> {
  // Step 1: ask our backend for a signed PUT URL.
  // The backend validates content type + size, mints the reference_id +
  // R2 key, and returns the URL we PUT to in step 2.
  const presignReq: PresignRequest = {
    filename: file.name,
    content_type: file.type,
    size_bytes: file.size,
  };
  const presigned = await apiPost<PresignRequest, PresignResponse>(
    "/references/presign",
    presignReq,
  );

  // Step 2: PUT the file body directly to R2.
  //
  // Important: the Content-Type header MUST match what the backend signed
  // for (presigned.content_type). The signature binds the value; any
  // mismatch yields SignatureDoesNotMatch and we'd waste both the user's
  // upload and a presign call. The browser also adds Content-Length
  // automatically from the Blob, which matches the size we signed.
  const r2Response = await fetch(presigned.upload_url, {
    method: "PUT",
    headers: { "Content-Type": presigned.content_type },
    body: file,
  });
  if (!r2Response.ok) {
    // R2's errors come back as XML. We don't try to parse them — surface
    // the status + body verbatim so debugging is unambiguous.
    const body = await r2Response.text().catch(() => "");
    throw new Error(
      `Direct upload to R2 failed: ${r2Response.status} ${r2Response.statusText}\n${body.slice(0, 500)}`,
    );
  }

  // Step 3: tell the backend the upload landed. Backend HEADs R2 to
  // verify the object's size matches what we declared, then INSERTs the
  // Reference row and returns it.
  const completeReq: CompleteRequest = {
    filename: file.name,
    content_type: presigned.content_type,
    size_bytes: presigned.size_bytes,
    key: presigned.key,
  };
  return apiPost<CompleteRequest, ReferenceResponse>(
    `/references/${presigned.reference_id}/complete`,
    completeReq,
  );
}
