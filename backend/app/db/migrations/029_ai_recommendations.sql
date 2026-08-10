-- AI Recommendations storage.
-- One row per (user_id, run_date) so a user has exactly one report per day.
-- Reports are regenerated on-demand (force_regenerate) or when a new day starts.

create table if not exists ai_recommendations (
    id              uuid         primary key default gen_random_uuid(),
    user_id         uuid         not null references users(id) on delete cascade,
    run_date        date         not null,
    report_json     jsonb        not null,
    generated_at    timestamptz  not null default now(),
    version         integer      not null default 1,
    constraint ai_recommendations_user_date_unique unique (user_id, run_date)
);

create index if not exists idx_ai_recommendations_user on ai_recommendations(user_id);
create index if not exists idx_ai_recommendations_user_date on ai_recommendations(user_id, run_date desc);

-- Cache table: always holds the latest report per user for fast reads.
create table if not exists ai_recommendations_cache (
    user_id         uuid         primary key references users(id) on delete cascade,
    run_date        date         not null,
    report_json     jsonb        not null,
    generated_at    timestamptz  not null default now(),
    latest_report_id uuid        references ai_recommendations(id) on delete set null
);

-- RLS policies
alter table ai_recommendations enable row level security;
alter table ai_recommendations_cache enable row level security;

create policy "Users can view their own AI recommendations"
    on ai_recommendations for select
    using (auth.uid() = user_id);

create policy "Users can insert their own AI recommendations"
    on ai_recommendations for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own AI recommendations"
    on ai_recommendations for update
    using (auth.uid() = user_id);

create policy "Users can delete their own AI recommendations"
    on ai_recommendations for delete
    using (auth.uid() = user_id);

create policy "Users can view their own AI recommendations cache"
    on ai_recommendations_cache for select
    using (auth.uid() = user_id);

create policy "Users can upsert their own AI recommendations cache"
    on ai_recommendations_cache for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own AI recommendations cache"
    on ai_recommendations_cache for update
    using (auth.uid() = user_id);
