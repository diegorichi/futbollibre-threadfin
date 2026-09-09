package com.futbol.tv;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class NavigationStateTest {
    @Test public void emptyListAlwaysSelectsZero() {
        assertEquals(0, NavigationState.clamp(4, 0));
        assertEquals(0, NavigationState.offsetFor(4, 0, 8, 5));
    }

    @Test public void selectionNeverLeavesList() {
        assertEquals(0, NavigationState.clamp(-1, 8));
        assertEquals(7, NavigationState.clamp(99, 8));
    }

    @Test public void offsetKeepsSelectedItemVisible() {
        assertEquals(0, NavigationState.offsetFor(2, 16, 8, 5));
        assertEquals(3, NavigationState.offsetFor(8, 16, 8, 5));
        assertEquals(8, NavigationState.offsetFor(15, 16, 8, 5));
    }
}
