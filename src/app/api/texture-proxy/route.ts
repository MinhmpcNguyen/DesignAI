import { NextRequest, NextResponse } from "next/server";

function isAllowedTextureUrl(rawUrl: string): boolean {
  try {
    const parsed = new URL(rawUrl);
    return (
      parsed.protocol === "https:" &&
      (parsed.hostname === "storage.mazig.io" ||
        parsed.hostname.endsWith(".storage.mazig.io"))
    );
  } catch {
    return false;
  }
}

export async function GET(request: NextRequest) {
  const rawUrl = request.nextUrl.searchParams.get("url");
  if (!rawUrl) {
    return NextResponse.json(
      { error: "Missing texture url" },
      { status: 400 },
    );
  }

  if (!isAllowedTextureUrl(rawUrl)) {
    return NextResponse.json({ error: "URL not allowed" }, { status: 400 });
  }

  try {
    const upstream = await fetch(rawUrl, {
      // Revalidate every 24h to reduce repeated bandwidth.
      next: { revalidate: 60 * 60 * 24 },
    });

    if (!upstream.ok) {
      return NextResponse.json(
        { error: `Upstream error: ${upstream.status}` },
        { status: 502 },
      );
    }

    const contentType = upstream.headers.get("content-type") ?? "image/webp";
    const imageBuffer = await upstream.arrayBuffer();

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "content-type": contentType,
        "cache-control": "public, max-age=86400, s-maxage=86400",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch texture" },
      { status: 502 },
    );
  }
}
