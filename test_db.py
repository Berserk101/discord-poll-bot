"""Quick smoke test for the database layer."""
import asyncio
import db


async def main():
    await db.init_db()
    print("DB initialized")

    # Create a poll
    poll_id = await db.create_poll(
        guild_id=123, channel_id=456, creator_id=789,
        title="Test Poll", max_picks=3, option_count=5,
    )
    print(f"Created poll #{poll_id}")

    # Add options
    opts = [{"option_num": i, "image_url": f"https://example.com/{i}.png"} for i in range(1, 6)]
    await db.add_options(poll_id, opts)
    print("Added 5 options")

    # Vote
    ok = await db.add_vote(poll_id, user_id=100, option_num=1, max_picks=3)
    print(f"Vote 1: {ok}")
    ok = await db.add_vote(poll_id, user_id=100, option_num=3, max_picks=3)
    print(f"Vote 2: {ok}")
    ok = await db.add_vote(poll_id, user_id=100, option_num=5, max_picks=3)
    print(f"Vote 3: {ok}")
    # This should fail (max 3)
    ok = await db.add_vote(poll_id, user_id=100, option_num=2, max_picks=3)
    print(f"Vote 4 (should be False): {ok}")

    # Check user votes
    votes = await db.get_user_votes(poll_id, user_id=100)
    print(f"User votes: {sorted(votes)}")

    # Tally
    tally = await db.get_tally(poll_id)
    print(f"Tally: {tally}")

    # Remove a vote
    await db.remove_vote(poll_id, user_id=100, option_num=3)
    votes = await db.get_user_votes(poll_id, user_id=100)
    print(f"After unvote: {sorted(votes)}")

    # Total voters
    total = await db.get_total_voters(poll_id)
    print(f"Total voters: {total}")

    # Cleanup
    await db.delete_poll(poll_id)
    print("Poll deleted")

    print("\nAll DB tests passed!")


asyncio.run(main())
