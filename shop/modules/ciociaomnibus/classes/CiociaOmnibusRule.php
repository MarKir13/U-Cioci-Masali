<?php
/**
 * The Omnibus rule (issue #72): the lowest price from the 30 days before a promotion started.
 *
 * Plain PHP without PrestaShop classes or the database, so tests/OmnibusRuleTest.php can run it on its own.
 * The module reads the price history and the promotion start, and passes them here.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class CiociaOmnibusRule
{
    public const WINDOW_DAYS = 30;

    /**
     * Counts every price in effect at some moment of the window [start - 30 days, start):
     * - the last price set before the window opened, as it was still in effect when the window opened;
     * - every price set inside the window.
     * Prices set at or after the start are skipped, including the promotion price itself.
     * With no price before the start (a promotion without any history), the regular price is the answer.
     *
     * @param array $history rows of ciocia_price_history, oldest first: ['price_gross' => ..., 'date_add' => ...]
     * @param DateTimeImmutable $promoStart when the promotion started
     * @param float $regularPrice the product price without the promotion
     */
    public static function lowestPrice(array $history, DateTimeImmutable $promoStart, float $regularPrice): float
    {
        $windowStart = $promoStart->modify('-' . self::WINDOW_DAYS . ' days');
        $priceWhenWindowOpened = null;
        $prices = [];

        foreach ($history as $row) {
            $date = new DateTimeImmutable($row['date_add']);
            if ($date >= $promoStart) {
                break;
            }
            if ($date <= $windowStart) {
                $priceWhenWindowOpened = (float) $row['price_gross'];
            } else {
                $prices[] = (float) $row['price_gross'];
            }
        }

        if ($priceWhenWindowOpened !== null) {
            $prices[] = $priceWhenWindowOpened;
        }

        return $prices === [] ? $regularPrice : min($prices);
    }
}
