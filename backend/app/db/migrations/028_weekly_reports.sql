-- Weekly AI Reports storage.
-- One row per (user_id, week_start) so a user has exactly one report per week.
-- Reports are deterministic (NO AI) and regenerated on-demand or weekly.

create table if not exists weekly_reports (
    id              uuid         primary key default gen_random_uuid(),
    user_id         uuid         not null references users(id) on delete cascade,
    week_start      date         not null,
    week_end        date         not null,
    report_json     jsonb        not null,
    generated_at    timestamptz  not null default now(),
    version         integer      not null default 1,
    constraint weekly_reports_user_week_unique unique (user_id, week_start)
);

create index if not exists idx_weekly_reports_user on weekly_reports(user_id);
create index if not exists idx_weekly_reports_user_week on weekly_reports(user_id, week_start desc);

-- Cache table: always holds the latest generated report per user for fast reads.
create table if not exists weekly_report_cache (
    user_id         uuid         primary key references users(id) on delete cascade,
    week_start      date         not null,
    week_end        date         not null,
    report_json     jsonb        not null,
    generated_at    timestamptz  not null default now(),
    latest_report_id uuid        references weekly_reports(id) on delete set null
);

-- RLS policies
alter table weekly_reports enable row level security;
alter table weekly_report_cache enable row level security;

create policy "Users can view their own weekly reports"
    on weekly_reports for select
    using (auth.uid() = user_id);

create policy "Users can insert their own weekly reports"
    on weekly_reports for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own weekly reports"
    on weekly_reports for update
    using (auth.uid() = user_id);

create policy "Users can delete their own weekly reports"
    on weekly_reports for delete
    using (auth.uid() = user_id);

create policy "Users can view their own weekly report cache"
    on weekly_report_cache for select
    using (auth.uid() = user_id);

create policy "Users can upsert their own weekly report cache"
    on weekly_report_cache for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own weekly report cache"
    on weekly_report_cache for update
    using (auth.uid() = user_id);
