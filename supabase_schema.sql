create table if not exists public.cars (
    name text primary key
);

create table if not exists public.refills (
    id bigint primary key,
    data date not null,
    cotxe text not null references public.cars(name),
    quilometratge numeric not null,
    litres numeric not null,
    preu_litre numeric not null,
    cost_total numeric not null,
    diposit_ple boolean not null,
    notes text not null default '',
    unique (cotxe, quilometratge)
);

alter table public.cars enable row level security;
alter table public.refills enable row level security;

insert into public.cars (name)
values ('Cotxe 1'), ('Cotxe 2')
on conflict (name) do nothing;
