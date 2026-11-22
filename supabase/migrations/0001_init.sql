-- =====================================================================
-- CivicScope AI — Supabase / PostgreSQL schema
-- Run once in: Supabase Dashboard -> SQL Editor -> New query -> Run
-- Safe to re-run (idempotent where possible).
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------- helpers ---------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ---------- 1. profiles -----------------------------------------------
create table if not exists public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  full_name     text,
  designation   text,
  organization  text,
  avatar_url    text,
  preferred_language text not null default 'en' check (preferred_language in ('en','hi','kn','ta','te','bn')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- auto-create a profile row whenever a user registers
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email,'@',1)))
  on conflict (id) do nothing;
  insert into public.user_settings (user_id) values (new.id) on conflict do nothing;
  return new;
end $$;

-- ---------- 13. user_settings (created early; trigger above uses it) --
create table if not exists public.user_settings (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  voice_enabled  boolean not null default false,
  voice_language text    not null default 'en' check (voice_language in ('en','hi','kn')),
  speech_rate    numeric(3,1) not null default 1.0 check (speech_rate between 0.5 and 2.0),
  speech_pitch   int     not null default 50 check (speech_pitch between 0 and 100),
  high_contrast  boolean not null default false,
  large_text     boolean not null default false,
  reduce_motion  boolean not null default false,
  notify_email   boolean not null default false,
  notify_in_app  boolean not null default true,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- 2. analyses -----------------------------------------------
-- One row per run of any module. Module-specific output lives in *_results.
create table if not exists public.analyses (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  module      text not null check (module in ('civicprobe','infoconflict','accessshadow','rulestress','promisetrace')),
  title       text not null,
  status      text not null default 'pending' check (status in ('pending','running','completed','failed')),
  error_message text,
  input_summary jsonb not null default '{}'::jsonb,
  started_at  timestamptz,
  completed_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists analyses_user_created_idx on public.analyses (user_id, created_at desc);
create index if not exists analyses_module_idx on public.analyses (user_id, module, status);

-- ---------- 3. sources ------------------------------------------------
create table if not exists public.sources (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  kind        text not null check (kind in ('url','pdf','document')),
  name        text not null,
  url         text,
  storage_path text,                 -- path inside the private Supabase Storage bucket
  mime_type   text,
  size_bytes  bigint,
  content_hash text,
  language    text,
  status      text not null default 'pending' check (status in ('pending','processing','ready','failed')),
  error_message text,
  page_count  int,
  fetched_at  timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists sources_user_idx on public.sources (user_id, created_at desc);
create index if not exists sources_hash_idx on public.sources (user_id, content_hash);

-- ---------- 4. source_chunks (RAG) ------------------------------------
create table if not exists public.source_chunks (
  id          uuid primary key default gen_random_uuid(),
  source_id   uuid not null references public.sources(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  chunk_index int  not null,
  content     text not null,
  page_number int,
  section_heading text,
  token_estimate int,
  tsv         tsvector generated always as (to_tsvector('simple', content)) stored,
  created_at  timestamptz not null default now(),
  unique (source_id, chunk_index)
);
create index if not exists source_chunks_source_idx on public.source_chunks (source_id, chunk_index);
create index if not exists source_chunks_tsv_idx on public.source_chunks using gin (tsv);

-- ---------- 5. civicprobe_results -------------------------------------
create table if not exists public.civicprobe_results (
  id          uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  source_id   uuid references public.sources(id) on delete set null,
  target_url  text not null,
  pages_scanned int not null default 0,
  links_checked int not null default 0,
  broken_links  int not null default 0,
  summary     text,
  health_score int check (health_score between 0 and 100),
  findings    jsonb not null default '[]'::jsonb,  -- [{type,severity,description,url,evidence,confidence}]
  created_at  timestamptz not null default now()
);
create index if not exists civicprobe_analysis_idx on public.civicprobe_results (analysis_id);
create index if not exists civicprobe_user_idx on public.civicprobe_results (user_id, created_at desc);

-- ---------- 6. infoconflict_results -----------------------------------
create table if not exists public.infoconflict_results (
  id          uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  topic       text,
  source_ids  uuid[] not null default '{}',
  summary     text,
  conflicts   jsonb not null default '[]'::jsonb,  -- [{field,severity,claims:[{source,value,evidence,page}],note}]
  agreements  jsonb not null default '[]'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists infoconflict_analysis_idx on public.infoconflict_results (analysis_id);
create index if not exists infoconflict_user_idx on public.infoconflict_results (user_id, created_at desc);

-- ---------- 7. accessshadow_results -----------------------------------
create table if not exists public.accessshadow_results (
  id          uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  source_id   uuid references public.sources(id) on delete set null,
  target      text not null,
  automated_findings jsonb not null default '[]'::jsonb,   -- deterministic checks
  manual_review_items jsonb not null default '[]'::jsonb,  -- needs a human / screen-reader test
  language_findings jsonb not null default '[]'::jsonb,
  counts      jsonb not null default '{}'::jsonb,
  summary     text,
  created_at  timestamptz not null default now()
);
create index if not exists accessshadow_analysis_idx on public.accessshadow_results (analysis_id);
create index if not exists accessshadow_user_idx on public.accessshadow_results (user_id, created_at desc);

-- ---------- 8. rulestress_results -------------------------------------
create table if not exists public.rulestress_results (
  id          uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  source_id   uuid references public.sources(id) on delete set null,
  scenario    text not null,
  verdict     text not null check (verdict in ('applies','does_not_apply','partially_applies','not_addressed','ambiguous')),
  answer      text not null,
  conditions  jsonb not null default '[]'::jsonb,   -- [{condition,status,evidence,page}]
  ambiguities jsonb not null default '[]'::jsonb,
  evidence    jsonb not null default '[]'::jsonb,
  confidence  text check (confidence in ('high','medium','low')),
  created_at  timestamptz not null default now()
);
create index if not exists rulestress_analysis_idx on public.rulestress_results (analysis_id);
create index if not exists rulestress_user_idx on public.rulestress_results (user_id, created_at desc);

-- ---------- 9. promisetrace_projects ----------------------------------
create table if not exists public.promisetrace_projects (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  analysis_id uuid references public.analyses(id) on delete set null,
  title       text not null,
  department  text,
  commitment_text text,
  announced_on date,
  target_date  date,
  status      text not null default 'no_update_found'
              check (status in ('on_track','delayed','completed','no_update_found','unclear')),
  evidence_summary text,
  source_ids  uuid[] not null default '{}',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists promise_projects_user_idx on public.promisetrace_projects (user_id, created_at desc);

-- ---------- 10. promise_milestones ------------------------------------
create table if not exists public.promise_milestones (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references public.promisetrace_projects(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  title       text not null,
  due_date    date,
  status      text not null default 'unknown' check (status in ('unknown','pending','in_progress','completed','delayed')),
  evidence    text,
  source_id   uuid references public.sources(id) on delete set null,
  page_number int,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists promise_milestones_project_idx on public.promise_milestones (project_id, due_date);

-- ---------- 11. reports -----------------------------------------------
create table if not exists public.reports (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  analysis_id uuid references public.analyses(id) on delete cascade,
  module      text not null,
  title       text not null,
  summary     text,
  severity_counts jsonb not null default '{}'::jsonb,
  body        jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists reports_user_idx on public.reports (user_id, created_at desc);

-- ---------- 12. notifications -----------------------------------------
create table if not exists public.notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  kind        text not null default 'info' check (kind in ('info','success','warning','error')),
  title       text not null,
  message     text,
  link        text,
  is_read     boolean not null default false,
  created_at  timestamptz not null default now()
);
create index if not exists notifications_user_idx on public.notifications (user_id, is_read, created_at desc);

-- ---------- updated_at triggers ---------------------------------------
do $$
declare t text;
begin
  foreach t in array array['profiles','user_settings','analyses','sources','promisetrace_projects','promise_milestones','reports']
  loop
    execute format('drop trigger if exists trg_%1$s_updated on public.%1$s', t);
    execute format('create trigger trg_%1$s_updated before update on public.%1$s for each row execute function public.set_updated_at()', t);
  end loop;
end $$;

-- =====================================================================
-- Row Level Security: every row is visible/editable only by its owner.
-- The FastAPI backend acts on behalf of the user (user JWT) for reads,
-- and uses the service-role key only for server-side jobs.
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array['analyses','sources','source_chunks','civicprobe_results','infoconflict_results',
                           'accessshadow_results','rulestress_results','promisetrace_projects',
                           'promise_milestones','reports','notifications']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "%1$s_owner_all" on public.%1$s', t);
    execute format($p$create policy "%1$s_owner_all" on public.%1$s
                      for all to authenticated
                      using (user_id = auth.uid()) with check (user_id = auth.uid())$p$, t);
  end loop;
end $$;

alter table public.profiles enable row level security;
drop policy if exists "profiles_owner_all" on public.profiles;
create policy "profiles_owner_all" on public.profiles
  for all to authenticated using (id = auth.uid()) with check (id = auth.uid());

alter table public.user_settings enable row level security;
drop policy if exists "user_settings_owner_all" on public.user_settings;
create policy "user_settings_owner_all" on public.user_settings
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- =====================================================================
-- Storage: private bucket for uploaded documents, per-user folders.
-- Object path convention: <user_id>/<source_id>/<filename>
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('civic-documents', 'civic-documents', false, 20971520,
        array['application/pdf','text/plain','text/html'])
on conflict (id) do nothing;

drop policy if exists "civic_docs_owner_select" on storage.objects;
drop policy if exists "civic_docs_owner_insert" on storage.objects;
drop policy if exists "civic_docs_owner_delete" on storage.objects;

create policy "civic_docs_owner_select" on storage.objects for select to authenticated
  using (bucket_id = 'civic-documents' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "civic_docs_owner_insert" on storage.objects for insert to authenticated
  with check (bucket_id = 'civic-documents' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "civic_docs_owner_delete" on storage.objects for delete to authenticated
  using (bucket_id = 'civic-documents' and (storage.foldername(name))[1] = auth.uid()::text);
