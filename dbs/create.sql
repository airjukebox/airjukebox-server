create table tbRequests
(
	DateTime timestamp with time zone default (now()),

	UserID text,
	LocationID text,
	SourceID text,
	TrackID text
);
