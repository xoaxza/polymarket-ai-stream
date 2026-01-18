import { NextRequest, NextResponse } from "next/server";

const VOTING_SERVER_URL = process.env.VOTING_SERVER_URL || "http://localhost:8080";

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        // Forward vote to Python voting server
        const response = await fetch(`${VOTING_SERVER_URL}/vote`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json();
            return NextResponse.json(error, { status: response.status });
        }

        const result = await response.json();
        return NextResponse.json(result);
    } catch (error) {
        return NextResponse.json(
            { error: "Voting server not available" },
            { status: 503 }
        );
    }
}
