import { NextRequest, NextResponse } from "next/server";
import { AccessToken } from "livekit-server-sdk";

export async function GET(request: NextRequest) {
    const apiKey = process.env.LIVEKIT_API_KEY;
    const apiSecret = process.env.LIVEKIT_API_SECRET;
    const wsUrl = process.env.LIVEKIT_URL;

    if (!apiKey || !apiSecret || !wsUrl) {
        return NextResponse.json(
            { error: "LiveKit credentials not configured" },
            { status: 500 }
        );
    }

    // Generate unique identity for this viewer
    const identity = `viewer-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const roomName = process.env.ROOM_NAME || "polymarket-ai-show";

    // Create access token with viewer-only permissions
    const at = new AccessToken(apiKey, apiSecret, {
        identity,
        name: `Viewer ${identity.slice(-6)}`,
        ttl: "2h", // Token valid for 2 hours
    });

    // Grant room join with subscribe-only permissions
    at.addGrant({
        room: roomName,
        roomJoin: true,
        canPublish: false,        // Viewers cannot publish
        canSubscribe: true,       // Viewers can subscribe to audio
        canPublishData: false,    // No data publishing
    });

    const token = await at.toJwt();

    return NextResponse.json({
        token,
        url: wsUrl,
        identity,
        roomName,
    });
}
