<?php $__env->startSection('title', $listing->title); ?>

<?php $__env->startSection('content'); ?>
    <?php $__env->startComponent('components.breadcrumb'); ?>
        <?php $__env->slot('li_1'); ?>
            <a href="<?php echo e(route('parts.index')); ?>"><?php echo e(__('Parts')); ?></a>
        <?php $__env->endSlot(); ?>
        <?php $__env->slot('title'); ?> <?php echo e(\Illuminate\Support\Str::limit($listing->title, 60)); ?> <?php $__env->endSlot(); ?>
    <?php echo $__env->renderComponent(); ?>

    <div class="row">
        <div class="col-lg-5">
            <div class="card">
                <div class="card-body bg-light text-center" style="min-height:400px;">
                    <?php if($listing->image_url): ?>
                        <img src="<?php echo e($listing->image_url); ?>" alt="" style="max-width:100%; max-height:380px; object-fit:contain;"
                             onerror="this.style.display='none'">
                    <?php else: ?>
                        <div class="d-flex align-items-center justify-content-center" style="height:380px;">
                            <i class="ri-image-line text-muted" style="font-size:6rem;"></i>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>

        <div class="col-lg-7">
            <div class="card">
                <div class="card-body">
                    <h4 class="mb-3"><?php echo e($listing->title); ?></h4>

                    <div class="d-flex gap-2 flex-wrap mb-3">
                        <span class="badge bg-light text-muted"><?php echo e($listing->source_name); ?></span>
                        <?php if($listing->condition): ?>
                            <span class="badge bg-info-subtle text-info"><?php echo e($listing->condition); ?></span>
                        <?php endif; ?>
                        <?php if($listing->category && $listing->category !== 'unknown'): ?>
                            <span class="badge bg-secondary-subtle text-secondary"><?php echo e($listing->category); ?></span>
                        <?php endif; ?>
                        <span class="badge bg-warning-subtle text-warning"><?php echo e(__('bike: :key', ['key' => $listing->bike_key])); ?></span>
                    </div>

                    <h2 class="mb-4">
                        <?php if($listing->price_amount !== null): ?>
                            <?php echo e(number_format((float) $listing->price_amount, 2)); ?>

                            <small class="text-muted fs-16"><?php echo e($listing->price_currency); ?></small>
                            <?php if($listing->shipping_amount): ?>
                                <small class="text-muted fs-13 d-block">+ <?php echo e(number_format((float) $listing->shipping_amount, 2)); ?> <?php echo e(__('shipping')); ?></small>
                            <?php endif; ?>
                        <?php else: ?>
                            <span class="text-muted fs-18"><?php echo e(__('Price not available')); ?></span>
                        <?php endif; ?>
                    </h2>

                    <a href="<?php echo e($listing->url); ?>" target="_blank" rel="noopener noreferrer"
                       class="btn btn-primary btn-lg mb-4">
                        <?php echo e(__('View on :source', ['source' => $listing->source_name])); ?>

                        <i class="ri-external-link-line ms-1"></i>
                    </a>

                    <dl class="row mb-0">
                        <?php if($listing->seller_name): ?>
                            <dt class="col-sm-3 text-muted"><?php echo e(__('Seller')); ?></dt>
                            <dd class="col-sm-9"><?php echo e($listing->seller_name); ?><?php echo e($listing->seller_country ? ' · ' . $listing->seller_country : ''); ?></dd>
                        <?php endif; ?>
                        <?php if($listing->part_number): ?>
                            <dt class="col-sm-3 text-muted"><?php echo e(__('Part #')); ?></dt>
                            <dd class="col-sm-9"><code><?php echo e($listing->part_number); ?></code></dd>
                        <?php endif; ?>
                        <dt class="col-sm-3 text-muted"><?php echo e(__('First seen')); ?></dt>
                        <dd class="col-sm-9"><?php echo e($listing->first_seen_at?->format('Y-m-d H:i')); ?></dd>
                        <dt class="col-sm-3 text-muted"><?php echo e(__('Last seen')); ?></dt>
                        <dd class="col-sm-9"><?php echo e($listing->last_seen_at?->format('Y-m-d H:i')); ?> (<?php echo e($listing->last_seen_at?->diffForHumans()); ?>)</dd>
                    </dl>
                </div>
            </div>
        </div>
    </div>

    <?php if($listing->description): ?>
        <div class="card">
            <div class="card-header"><h5 class="mb-0"><?php echo e(__('Description')); ?></h5></div>
            <div class="card-body" style="white-space:pre-wrap;"><?php echo e($listing->description); ?></div>
        </div>
    <?php endif; ?>

    <?php if($listing->fitment_text): ?>
        <div class="card">
            <div class="card-header"><h5 class="mb-0"><?php echo e(__('Fitment')); ?></h5></div>
            <div class="card-body" style="white-space:pre-wrap;"><?php echo e($listing->fitment_text); ?></div>
        </div>
    <?php endif; ?>

    <?php if($listing->snapshots->isNotEmpty()): ?>
        <div class="card">
            <div class="card-header"><h5 class="mb-0"><?php echo e(__('Price history')); ?></h5></div>
            <div class="card-body p-0">
                <table class="table mb-0">
                    <thead><tr><th><?php echo e(__('Checked')); ?></th><th class="text-end"><?php echo e(__('Price')); ?></th><th><?php echo e(__('Availability')); ?></th></tr></thead>
                    <tbody>
                    <?php $__currentLoopData = $listing->snapshots; $__env->addLoop($__currentLoopData); foreach($__currentLoopData as $s): $__env->incrementLoopIndices(); $loop = $__env->getLastLoop(); ?>
                        <tr>
                            <td><?php echo e($s->checked_at?->format('Y-m-d H:i')); ?></td>
                            <td class="text-end">
                                <?php if($s->price_amount !== null): ?>
                                    <?php echo e(number_format((float) $s->price_amount, 2)); ?> <?php echo e($listing->price_currency); ?>

                                <?php else: ?>
                                    <span class="text-muted">—</span>
                                <?php endif; ?>
                            </td>
                            <td><?php echo e($s->availability_status ?? '—'); ?></td>
                        </tr>
                    <?php endforeach; $__env->popLoop(); $loop = $__env->getLastLoop(); ?>
                    </tbody>
                </table>
            </div>
        </div>
    <?php endif; ?>
<?php $__env->stopSection(); ?>

<?php echo $__env->make('layouts.master', array_diff_key(get_defined_vars(), ['__data' => 1, '__path' => 1]))->render(); ?><?php /**PATH /Users/cybersaint/Sites/WebCrawler/console/resources/views/parts/show.blade.php ENDPATH**/ ?>