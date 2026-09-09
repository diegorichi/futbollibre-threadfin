package com.futbol.tv;

/** Pure navigation calculations shared by the TV screen and its tests. */
public final class NavigationState {
    private NavigationState() { }

    public static int clamp(int value, int size) {
        return size == 0 ? 0 : Math.max(0, Math.min(size - 1, value));
    }

    public static int offsetFor(int selected, int size, int visibleItems, int focusPosition) {
        int maxOffset = Math.max(0, size - visibleItems);
        return Math.max(0, Math.min(maxOffset, selected - focusPosition));
    }
}
