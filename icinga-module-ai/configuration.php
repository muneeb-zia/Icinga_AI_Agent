<?php

/** @var \Icinga\Application\Modules\Module $this */

// Register the frontend logic
$this->provideHook('monitoring/HostDetailExtension');
$this->provideHook('monitoring/ServiceDetailExtension');

// The hooks will load our Javascript/HTML directly into the detail views.
