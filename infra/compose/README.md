# Infrastructure workspace

Az FND-015–017 itt hozza létre a Qdrant Compose-konfigurációját, named volume-ját és kapcsolattesztjét. Jelenleg nincs indítható infrastruktúra.

A Qdrant csak `127.0.0.1:6333` címen publikálható. A normál leállítás megőrzi a volume-ot. A FastAPI és a Next.js a hoston fut, nem kap alkalmazáskonténert.

A későbbi Compose-parancsok explicit `--env-file` és `--file` útvonalat használnak a repository gyökeréhez képest. A `.env` nem shell script.
