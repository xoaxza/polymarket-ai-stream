import { NextRequest, NextResponse } from "next/server";

const VOTING_SERVER_URL = process.env.VOTING_SERVER_URL || "http://localhost:8080";

export async function GET() {
    try {
        const response = await fetch(`${VOTING_SERVER_URL}/state`, {
            cache: "no-store",
        });

        if (!response.ok) {
            return NextResponse.json(
                { error: "Failed to fetch state from voting server" },
                { status: 502 }
            );
        }

        const state = await response.json();
        return NextResponse.json(state);
    } catch (error) {
        return NextResponse.json(
            { error: "Voting server not available" },
            { status: 503 }
        );
    }
}
